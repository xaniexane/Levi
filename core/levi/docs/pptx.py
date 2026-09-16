"""LEVI-native ``.pptx`` read/create — stdlib only (``zipfile`` + ``xml.etree``).

A ``.pptx`` file is a zip archive of XML parts (OOXML PresentationML).
Creating a deck needs a full relationship chain — presentation →
slides → slide layout → slide master → theme — so this module writes a
*minimal valid* set of parts: one master, one layout, one theme, and one
slide part per slide (title + bullet shapes).

Honest limits
-------------
* Reading: shape text only (paragraphs of ``a:t`` runs, in document
  order per shape). No images, no notes, no animations, no embedded
  media, no master-placed text.
* Writing: title slides and title-plus-bullet slides only. The
  generated deck opens in PowerPoint/LibreOffice/Google Slides.

Everything here is written from the OOXML structure itself; no other
product's code or branding is involved.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

DOC_REL = f"{R_NS}/officeDocument"
SLIDE_REL = f"{R_NS}/slide"
LAYOUT_REL = f"{R_NS}/slideLayout"
MASTER_REL = f"{R_NS}/slideMaster"
THEME_REL = f"{R_NS}/theme"

PathLike = Union[str, Path]

# A slide is (title, bullets). Dicts {"title": ..., "bullets": [...]} accepted.
SlideSpec = Union[Tuple[Optional[str], Sequence[str]], dict]


def _p(tag: str) -> str:
    return f"{{{P_NS}}}{tag}"


def _a(tag: str) -> str:
    return f"{{{A_NS}}}{tag}"


def _r(attrib: str) -> str:
    return f"{{{R_NS}}}{attrib}"


_NS_DECL = f'xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}"'


@dataclass
class PptxSlide:
    """One slide: list of shapes, each a list of paragraph texts."""

    shapes: List[List[str]] = field(default_factory=list)


@dataclass
class PptxDeck:
    """A deck: slides in presentation order."""

    slides: List[PptxSlide] = field(default_factory=list)

    def text(self) -> str:
        """All slide text, slides separated by blank lines."""
        blocks = []
        for slide in self.slides:
            blocks.append("\n".join(" ".join(shape) for shape in slide.shapes))
        return "\n\n".join(blocks)


def _norm_slide(spec: SlideSpec) -> Tuple[Optional[str], List[str]]:
    if isinstance(spec, dict):
        title = spec.get("title")
        bullets = spec.get("bullets") or []
    else:
        title, bullets = spec
    title_s = None if title is None else str(title)
    return title_s, [str(b) for b in bullets]


def _paragraph_xml(text: str, size: int, bold: bool, bullet: bool) -> str:
    rpr = f'<a:rPr lang="en-US" sz="{size * 100}"'
    if bold:
        rpr += ' b="1"'
    rpr += "/>"
    ppr = '<a:pPr><a:buChar char="•"/></a:pPr>' if bullet else "<a:pPr/>"
    return (
        f"<a:p>{ppr}<a:r>{rpr}"
        f'<a:t xml:space="preserve">{escape(text)}</a:t>'
        "</a:r></a:p>"
    )


def _shape_xml(
    shape_id: int,
    name: str,
    ph_type: Optional[str],
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: Sequence[str],
    size: int,
    bold: bool,
    bullet: bool,
) -> str:
    ph = f'<p:nvPr><p:ph type="{ph_type}"/></p:nvPr>' if ph_type else "<p:nvPr/>"
    paras = "".join(
        _paragraph_xml(p, size, bold, bullet) for p in paragraphs if p != ""
    )
    if not paras:
        paras = '<a:p><a:endParaRPr lang="en-US"/></a:p>'
    return (
        "<p:sp>"
        "<p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        "<p:cNvSpPr/>"
        f"{ph}"
        "</p:nvSpPr>"
        "<p:spPr>"
        f'<a:xfrm><a:off x="{x}" y="{y}"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</p:spPr>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody>"
        "</p:sp>"
    )


def _slide_xml(title: Optional[str], bullets: Sequence[str]) -> str:
    shapes = []
    if title:
        shapes.append(
            _shape_xml(
                2,
                "Title 1",
                "title",
                685800,
                365760,
                7772400,
                1473120,
                [title],
                32,
                True,
                False,
            )
        )
    if bullets:
        shapes.append(
            _shape_xml(
                3,
                "Content Placeholder 2",
                "body",
                685800,
                2133600,
                7772400,
                2734560,
                list(bullets),
                18,
                False,
                True,
            )
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<p:sld {_NS_DECL}>"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr>"
        '<p:cNvPr id="1" name=""/>'
        "<p:cNvGrpSpPr/><p:nvPr/>"
        "</p:nvGrpSpPr>"
        "<p:grpSpPr>"
        "<a:xfrm>"
        '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
        "</a:xfrm>"
        "</p:grpSpPr>"
        f"{''.join(shapes)}"
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


_LAYOUT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<p:sldLayout {_NS_DECL} type="titleAndContent" preserve="1">'
    '<p:cSld name="Title and Content"><p:spTree>'
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
    "<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
    "<p:grpSpPr><a:xfrm>"
    '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
    "</a:xfrm></p:grpSpPr>"
    "</p:spTree></p:cSld>"
    "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
    "</p:sldLayout>"
)

_MASTER_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f"<p:sldMaster {_NS_DECL}>"
    "<p:cSld>"
    '<p:bg><p:bgPr><a:solidFill><a:schemeClr val="lt1"/></a:solidFill>'
    "</p:bgPr></p:bg>"
    "<p:spTree>"
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
    "<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
    "<p:grpSpPr><a:xfrm>"
    '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
    "</a:xfrm></p:grpSpPr>"
    "</p:spTree>"
    "</p:cSld>"
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" '
    'accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent5" accent6="accent6" '
    'hlink="hlink" folHlink="folHlink"/>'
    "<p:sldLayoutIdLst>"
    '<p:sldLayoutId id="2147483649" r:id="rId1"/>'
    "</p:sldLayoutIdLst>"
    "<p:txStyles>"
    '<p:titleStyle><a:lvl1pPr><a:defRPr sz="4400"/></a:lvl1pPr></p:titleStyle>'
    '<p:bodyStyle><a:lvl1pPr><a:defRPr sz="3200"/></a:lvl1pPr></p:bodyStyle>'
    '<p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>'
    "</p:txStyles>"
    "</p:sldMaster>"
)

_THEME_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<a:theme xmlns:a="{A_NS}" name="LEVI Minimal Theme">'
    "<a:themeElements>"
    '<a:clrScheme name="Office">'
    '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="1F497D"/></a:dk2>'
    '<a:lt2><a:srgbClr val="EEECE1"/></a:lt2>'
    '<a:accent1><a:srgbClr val="4F81BD"/></a:accent1>'
    '<a:accent2><a:srgbClr val="C0504D"/></a:accent2>'
    '<a:accent3><a:srgbClr val="9BBB59"/></a:accent3>'
    '<a:accent4><a:srgbClr val="806000"/></a:accent4>'
    '<a:accent5><a:srgbClr val="4BACC6"/></a:accent5>'
    '<a:accent6><a:srgbClr val="F79646"/></a:accent6>'
    '<a:hlink><a:srgbClr val="0000FF"/></a:hlink>'
    '<a:folHlink><a:srgbClr val="800080"/></a:folHlink>'
    "</a:clrScheme>"
    '<a:fmtScheme name="Office">'
    "<a:fillStyleLst>"
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    "</a:fillStyleLst>"
    "<a:lnStyleLst>"
    "<a:ln><a:noFill/></a:ln><a:ln><a:noFill/></a:ln><a:ln><a:noFill/></a:ln>"
    "</a:lnStyleLst>"
    "<a:effectStyleLst>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "</a:effectStyleLst>"
    "<a:bgFillStyleLst>"
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    "</a:bgFillStyleLst>"
    "</a:fmtScheme>"
    "</a:themeElements>"
    "</a:theme>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{DOC_REL}" Target="ppt/presentation.xml"/>'
    "</Relationships>"
)

_SLIDE_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{LAYOUT_REL}" '
    'Target="../slideLayouts/slideLayout1.xml"/>'
    "</Relationships>"
)

_LAYOUT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{MASTER_REL}" '
    'Target="../slideMasters/slideMaster1.xml"/>'
    "</Relationships>"
)

_MASTER_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<Relationships xmlns="{RELS_NS}">'
    f'<Relationship Id="rId1" Type="{LAYOUT_REL}" '
    'Target="../slideLayouts/slideLayout1.xml"/>'
    f'<Relationship Id="rId2" Type="{THEME_REL}" Target="../theme/theme1.xml"/>'
    "</Relationships>"
)

_PRESENTATION_CT = (
    '<Override PartName="/ppt/presentation.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'presentationml.presentation.main+xml"/>'
)
_SLIDE_CT = (
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'presentationml.slide+xml"'
)
_LAYOUT_CT = (
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'presentationml.slideLayout+xml"'
)
_MASTER_CT = (
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'presentationml.slideMaster+xml"'
)
_THEME_CT = 'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"'


def _content_types(slide_count: int) -> str:
    overrides = [_PRESENTATION_CT]
    for i in range(1, slide_count + 1):
        overrides.append(f'<Override PartName="/ppt/slides/slide{i}.xml" {_SLIDE_CT}/>')
    overrides.append(
        f'<Override PartName="/ppt/slideLayouts/slideLayout1.xml" {_LAYOUT_CT}/>'
    )
    overrides.append(
        f'<Override PartName="/ppt/slideMasters/slideMaster1.xml" {_MASTER_CT}/>'
    )
    overrides.append(f'<Override PartName="/ppt/theme/theme1.xml" {_THEME_CT}/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Types xmlns="{CT_NS}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{''.join(overrides)}"
        "</Types>"
    )


def _presentation_xml(slide_count: int) -> str:
    sld_ids = "".join(
        f'<p:sldId id="{256 + i}" r:id="rId{i + 2}"/>' for i in range(slide_count)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<p:presentation {_NS_DECL}>"
        "<p:sldMasterIdLst>"
        '<p:sldMasterId id="2147483648" r:id="rId1"/>'
        "</p:sldMasterIdLst>"
        f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
        '<p:sldSz cx="9144000" cy="5143500" type="wide"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )


def _presentation_rels(slide_count: int) -> str:
    rels = [
        f'<Relationship Id="rId1" Type="{MASTER_REL}" '
        'Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(1, slide_count + 1):
        rels.append(
            f'<Relationship Id="rId{i + 1}" Type="{SLIDE_REL}" '
            f'Target="slides/slide{i}.xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{RELS_NS}">{"".join(rels)}</Relationships>'
    )


def write_pptx(
    path: PathLike,
    title: Optional[str] = None,
    slides: Sequence[SlideSpec] = (),
) -> Path:
    """Create a minimal valid ``.pptx`` deck.

    ``slides`` is a sequence of ``(title, bullets)`` tuples (or dicts
    with ``title``/``bullets`` keys). When no slides are given, a single
    title slide is created from ``title``. Returns the written path.
    """
    out = Path(path)
    norm = [_norm_slide(s) for s in slides]
    if not norm:
        norm = [(str(title) if title else "Untitled", [])]
    count = len(norm)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(count))
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("ppt/presentation.xml", _presentation_xml(count))
        zf.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels(count))
        for i, (s_title, bullets) in enumerate(norm, start=1):
            zf.writestr(f"ppt/slides/slide{i}.xml", _slide_xml(s_title, bullets))
            zf.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", _SLIDE_RELS)
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", _LAYOUT_XML)
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _LAYOUT_RELS)
        zf.writestr("ppt/slideMasters/slideMaster1.xml", _MASTER_XML)
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _MASTER_RELS)
        zf.writestr("ppt/theme/theme1.xml", _THEME_XML)
    return out


def _rels_target(raw: bytes, rel_id: str) -> Optional[str]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    ns = {"r": RELS_NS}
    for rel in root.findall("r:Relationship", ns):
        if rel.get("Id") == rel_id:
            return rel.get("Target")
    return None


def _resolve(base_dir: str, target: str) -> str:
    parts = (base_dir.rstrip("/") + "/" + target).split("/")
    stack: List[str] = []
    for part in parts:
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)


def read_pptx(path: PathLike) -> PptxDeck:
    """Read slide text from a ``.pptx`` file, in presentation order.

    Raises :class:`ValueError` when the file is not a readable ``.pptx``.
    """
    src = Path(path)
    try:
        zf = zipfile.ZipFile(src, "r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{src} is not a zip-based .pptx file: {exc}") from exc
    with zf:
        try:
            pres_raw = zf.read("ppt/presentation.xml")
            pres_rels = zf.read("ppt/_rels/presentation.xml.rels")
        except KeyError as exc:
            raise ValueError(
                f"{src} is not a .pptx file (no ppt/presentation.xml)"
            ) from exc
        try:
            pres_root = ET.fromstring(pres_raw)
        except ET.ParseError as exc:
            raise ValueError(
                f"{src}: ppt/presentation.xml is not valid XML: {exc}"
            ) from exc
        slide_parts: List[str] = []
        sld_id_lst = pres_root.find(_p("sldIdLst"))
        if sld_id_lst is not None:
            for sld_id in sld_id_lst.findall(_p("sldId")):
                rel_id = sld_id.get(_r("id")) or ""
                target = _rels_target(pres_rels, rel_id)
                if target:
                    slide_parts.append(_resolve("ppt", target))
        deck = PptxDeck()
        for part in slide_parts:
            try:
                slide_raw = zf.read(part)
            except KeyError:
                continue
            try:
                slide_root = ET.fromstring(slide_raw)
            except ET.ParseError:
                continue
            slide = PptxSlide()
            tree = slide_root.find(f"{_p('cSld')}/{_p('spTree')}")
            if tree is not None:
                for sp in tree.findall(_p("sp")):
                    tx_body = sp.find(_p("txBody"))
                    if tx_body is None:
                        continue
                    paras = []
                    for a_p in tx_body.findall(_a("p")):
                        paras.append("".join(t.text or "" for t in a_p.iter(_a("t"))))
                    slide.shapes.append(paras)
            deck.slides.append(slide)
    return deck
