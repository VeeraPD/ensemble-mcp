"""Path policy: what sub-agents may read and write. This is the safety core."""
import fnmatch
import os

# Never readable as context and never writable, whatever a role owns.
SECRET_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "id_rsa*", "id_ed25519*", "*.keystore", "credentials*")
PROTECTED_DIRS = (".git", ".ensemble")


class PathError(ValueError):
    pass


def _is_secret(rel):
    base = os.path.basename(rel)
    return any(fnmatch.fnmatch(base, pat) for pat in SECRET_PATTERNS)


def _in_protected_dir(rel):
    return rel.split(os.sep)[0] in PROTECTED_DIRS


def _under(rel, owned):
    return rel == owned or rel.startswith(owned + os.sep)


def _inside(root, full):
    return full == root or full.startswith(root + os.sep)


def resolve_read(cfg, rel):
    """Return (rel, absolute) for a project-relative file a sub-agent may see."""
    rel = os.path.normpath(rel)
    if os.path.isabs(rel) or rel == ".." or rel.startswith(".." + os.sep):
        raise PathError(f"context path not allowed: {rel}")
    full = os.path.realpath(os.path.join(cfg.root, rel))
    real_rel = os.path.relpath(full, cfg.root)
    if not _inside(cfg.root, full) or _is_secret(real_rel) or _in_protected_dir(real_rel):
        raise PathError(f"context path not allowed: {rel}")
    return rel, full


def resolve_write(cfg, role, rel):
    """Return (rel, absolute) for a file `role` may write, or raise PathError."""
    owned = cfg.roles[role].owns
    rel = os.path.normpath(rel)
    if os.path.isabs(rel) or rel == ".." or rel.startswith(".." + os.sep):
        raise PathError("path escapes project")
    full = os.path.realpath(os.path.join(cfg.root, rel))
    if not _inside(cfg.root, full):
        raise PathError("path escapes project (symlink?)")
    real_rel = os.path.relpath(full, cfg.root)
    # Check both the spelled path and where it really lands, so symlinks cannot launder a write.
    for candidate in (rel, real_rel):
        if _is_secret(candidate) or _in_protected_dir(candidate):
            raise PathError(f"'{rel}' is protected")
        if not any(_under(candidate, o) for o in owned):
            raise PathError(f"role '{role}' may not write '{rel}' (owns {owned})")
    if os.path.realpath(cfg.path) == full:
        raise PathError("the config file is protected")
    return rel, full
