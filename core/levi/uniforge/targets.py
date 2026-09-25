"""UniForge target definitions.

Each target declares its tool requirements HONESTLY. ``required_tools``
are executables that must exist on PATH; the executor refuses to run a
plan cleanly — with a receipt naming the missing tools — instead of ever
faking a build. Steps are real commands: when a run goes live, what you
see in the preview is what executes.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List

from .plan import Step

# Inline hermetic check/render scripts. They run under ``python3 -c`` so
# the only declared tool is python3 itself; stdlib only, no network.

_LAYOUT_CHECK = (
    "import os,sys;"
    "r=os.getcwd();"
    "files=set(os.listdir(r));"
    "ok=bool(files & {'setup.py','pyproject.toml','setup.cfg','PKG-INFO'})"
    " or any(os.path.isdir(os.path.join(r,d)) and "
    "__import__('glob').glob(os.path.join(r,d,'*','__init__.py')) "
    "for d in ('src',))"
    " or bool(__import__('glob').glob(os.path.join(r,'*','__init__.py')));"
    "print('layout ok' if ok else 'no python package layout found');"
    "sys.exit(0 if ok else 1)"
)

_MANIFEST_WRITE = (
    "import os,sys,glob;"
    "mods=sorted(p for p in glob.glob('**/*.py',recursive=True)"
    " if os.path.sep+'__pycache__'+os.path.sep not in p);"
    "os.makedirs('dist',exist_ok=True);"
    "open('dist/BUILD_MANIFEST.txt','w').write("
    "'modules: %d\\n' % len(mods)+'\\n'.join(mods)+'\\n');"
    "print('manifest: %d modules' % len(mods))"
)

_PAGES_CHECK = (
    "import sys,glob;"
    "pages=glob.glob('*.md')+glob.glob('*.txt');"
    "print('pages: %d' % len(pages));"
    "sys.exit(0 if pages else 1)"
)

_SITE_RENDER = (
    "import os,glob,html;"
    "pages=sorted(glob.glob('*.md')+glob.glob('*.txt'));"
    "os.makedirs('dist',exist_ok=True);"
    "def render(p):"
    " b=open(p,encoding='utf-8').read();"
    " ps=''.join('<p>%s</p>'%html.escape(x.strip())"
    "  for x in b.split('\\n\\n') if x.strip());"
    " return '<!doctype html><html><head><meta charset=utf-8>'"
    "  '<title>%s</title></head><body>%s</body></html>'%(html.escape(p),ps);"
    "[open('dist/'+os.path.splitext(os.path.basename(p))[0]+'.html','w',"
    " encoding='utf-8').write(render(p)) for p in pages];"
    "open('dist/index.html','w',encoding='utf-8').write("
    " '<!doctype html><html><head><meta charset=utf-8><title>index</title>'"
    " '</head><body><ul>'+''.join("
    " '<li><a href=\"%s\">%s</a></li>'%("
    "  os.path.splitext(os.path.basename(p))[0]+'.html',"
    "  html.escape(p)) for p in pages)+'</ul></body></html>');"
    "print('rendered %d pages' % len(pages))"
)

_SCAFFOLD_CHECK = (
    "import os,sys;"
    "r=os.getcwd();"
    "files=set(os.listdir(r));"
    "ok=bool(files & {'settings.gradle','build.gradle','build.gradle.kts',"
    " 'settings.gradle.kts'});"
    "print('scaffold ok' if ok else 'no gradle scaffold found');"
    "sys.exit(0 if ok else 1)"
)


def _python_package_steps(workdir: str, plan_name: str) -> List[Step]:
    return [
        Step(
            id="python-package:1-verify-layout",
            label="verify python package layout",
            target="python-package",
            tool="python3",
            argv=["python3", "-c", _LAYOUT_CHECK],
            workdir=workdir,
        ),
        Step(
            id="python-package:2-compile",
            label="byte-compile all modules",
            target="python-package",
            tool="python3",
            argv=["python3", "-m", "compileall", "-q", "."],
            workdir=workdir,
            depends_on=["python-package:1-verify-layout"],
        ),
        Step(
            id="python-package:3-manifest",
            label="write build manifest artifact",
            target="python-package",
            tool="python3",
            argv=["python3", "-c", _MANIFEST_WRITE],
            workdir=workdir,
            depends_on=["python-package:2-compile"],
            artifacts=["dist/BUILD_MANIFEST.txt"],
        ),
    ]


def _static_site_steps(workdir: str, plan_name: str) -> List[Step]:
    return [
        Step(
            id="static-site:1-verify-pages",
            label="verify page sources exist",
            target="static-site",
            tool="python3",
            argv=["python3", "-c", _PAGES_CHECK],
            workdir=workdir,
        ),
        Step(
            id="static-site:2-render",
            label="render pages to static html (plain-text render)",
            target="static-site",
            tool="python3",
            argv=["python3", "-c", _SITE_RENDER],
            workdir=workdir,
            depends_on=["static-site:1-verify-pages"],
            artifacts=["dist/index.html"],
        ),
    ]


def _android_apk_scaffold_steps(workdir: str, plan_name: str) -> List[Step]:
    return [
        Step(
            id="android-apk-scaffold:1-verify-scaffold",
            label="verify gradle scaffold present",
            target="android-apk-scaffold",
            tool="python3",
            argv=["python3", "-c", _SCAFFOLD_CHECK],
            workdir=workdir,
        ),
        Step(
            id="android-apk-scaffold:2-assemble",
            label="gradle assembleDebug (offline: no network)",
            target="android-apk-scaffold",
            tool="gradle",
            argv=["gradle", "assembleDebug", "--offline"],
            workdir=workdir,
            depends_on=["android-apk-scaffold:1-verify-scaffold"],
            consequential=True,
            artifacts=["app/build/outputs/apk/debug/app-debug.apk"],
        ),
    ]


StepFactory = Callable[[str, str], List[Step]]

#: Target registry. ``required_tools`` is the honesty contract: every
#: executable a target's steps need. Optional tools are nice-to-have.
TARGETS: Dict[str, Dict[str, object]] = {
    "python-package": {
        "id": "python-package",
        "name": "Python package",
        "description": (
            "Verify layout, byte-compile every module, and emit a real "
            "build manifest artifact. Hermetic and stdlib-only."
        ),
        "required_tools": ["python3"],
        "optional_tools": [],
        "honesty_note": (
            "No wheel/sdist is produced: building one needs a backend "
            "(setuptools/build) we do not assume. The manifest artifact "
            "is the honest output of this target."
        ),
        "make_steps": _python_package_steps,
    },
    "static-site": {
        "id": "static-site",
        "name": "Static site",
        "description": (
            "Render .md/.txt pages to static HTML with a plain-text "
            "renderer (paragraphs wrapped, HTML-escaped). Real output, "
            "no fake markdown engine claims."
        ),
        "required_tools": ["python3"],
        "optional_tools": [],
        "honesty_note": (
            "The renderer is intentionally minimal — it does not claim "
            "full markdown support. What it does, it does for real."
        ),
        "make_steps": _static_site_steps,
    },
    "android-apk-scaffold": {
        "id": "android-apk-scaffold",
        "name": "Android APK scaffold",
        "description": (
            "Verify a Gradle scaffold exists, then assembleDebug. "
            "Runs gradle --offline so a build can never silently reach "
            "the network; missing java/gradle refuses cleanly."
        ),
        "required_tools": ["python3", "java", "gradle"],
        "optional_tools": ["adb"],
        "honesty_note": (
            "This target cannot conjure an APK from nothing: without a "
            "real Gradle scaffold plus java and gradle on PATH, it "
            "refuses with a receipt instead of faking a build."
        ),
        "make_steps": _android_apk_scaffold_steps,
    },
}


def target_ids() -> List[str]:
    """Registered target ids, sorted."""
    return sorted(TARGETS)


def validate_target_ids(ids: List[str]) -> List[str]:
    """Return ids as given; raise ``ValueError`` naming unknown ones."""
    unknown = [i for i in ids if i not in TARGETS]
    if unknown:
        raise ValueError(
            "unknown target(s): %s (known: %s)"
            % (", ".join(unknown), ", ".join(target_ids()))
        )
    return list(ids)


def make_steps(target_id: str, workdir: str, plan_name: str) -> List[Step]:
    """Build the steps for one target (workdir must be absolute)."""
    validate_target_ids([target_id])
    factory = TARGETS[target_id]["make_steps"]
    assert isinstance(factory, type(_python_package_steps)) or callable(factory)
    steps: List[Step] = factory(os.path.abspath(workdir), plan_name)
    return steps
