"""LEVI off-machine backup pipeline.

Snapshots ``~/.levi`` into timestamped, hash-manifested tarballs and ships
them off-machine through rclone — always behind rclone's ``crypt`` overlay
(client-side encryption), so the remote backend only ever sees ciphertext.

Submodules:
    config    paths, config/state files, rclone discovery (no secrets stored)
    snapshot  create / list / verify / prune local snapshots
    sync      rclone copy to the crypt remote (GCS primary, archive.org fallback)
    restore   download, verify, stage; --apply only with explicit confirmation
    cli       ``levi backup`` command wiring
    daily     the once-a-day job: snapshot always, sync when configured
"""
