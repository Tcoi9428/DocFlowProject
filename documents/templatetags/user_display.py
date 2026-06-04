from django import template

from documents.user_display import user_full_name, user_identity, user_position

register = template.Library()


@register.filter
def user_name(user):
    return user_full_name(user)


@register.filter
def user_job(user):
    return user_position(user)


@register.filter
def user_label(user):
    return user_identity(user)
