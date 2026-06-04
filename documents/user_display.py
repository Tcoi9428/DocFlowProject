def user_full_name(user):
    if not user:
        return "-"

    profile = getattr(user, "userprofile", None)
    parts = [
        getattr(user, "last_name", ""),
        getattr(user, "first_name", ""),
        getattr(profile, "patronymic", "") if profile else "",
    ]
    name = " ".join(part.strip() for part in parts if part and part.strip())
    return name or getattr(user, "username", "") or "-"


def user_position(user):
    if not user:
        return ""

    profile = getattr(user, "userprofile", None)
    return getattr(profile, "position", "") if profile else ""


def user_identity(user):
    name = user_full_name(user)
    position = user_position(user)
    return f"{name} ({position})" if position else name
