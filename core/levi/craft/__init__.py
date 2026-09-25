"""craft — the guild quarter.

Dead craft knowledge reborn as LEVI-native additions (hunt wave-014,
"lost crafts"). Not replicas: the mechanisms are clean-room remixes,
stdlib-only, local-first.

  hallmark  struck provenance — maker's mark + independent verifier +
            SHA-256 + date letter, sidecarred onto any artifact;
            consequential flows refuse unhallmarked records (deny-closed).
  guild     the indenture ladder — apprentice (read-only) -> journeyman
            (writes with confirmation) -> master (autonomous), earned by
            logged practice, mentor sign-off, and a peer-judged
            masterpiece retained in the guildhall corpus.
  measures  the museum of dead measures — historical units with
            master-standard provenance; Gunter's decimal chain trick and
            the Egyptian seked included.
"""

from . import guild, hallmark, measures

__all__ = ["guild", "hallmark", "measures"]
