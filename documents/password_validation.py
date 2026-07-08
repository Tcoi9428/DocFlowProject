import re

from django.core.exceptions import ValidationError


class LatinLettersAndDigitsPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 4:
            raise ValidationError("Пароль должен содержать не менее 4 символов.")
        if not re.fullmatch(r"[A-Za-z0-9]+", password):
            raise ValidationError("Используйте только латинские буквы и цифры.")
        if not re.search(r"[A-Za-z]", password):
            raise ValidationError("Пароль должен содержать хотя бы одну латинскую букву.")
        if not re.search(r"\d", password):
            raise ValidationError("Пароль должен содержать хотя бы одну цифру.")

    def get_help_text(self):
        return "Пароль: минимум 4 символа, только латинские буквы и цифры, нужна хотя бы одна буква и одна цифра."
