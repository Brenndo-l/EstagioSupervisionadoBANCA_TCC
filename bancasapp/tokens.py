from django.contrib.auth.tokens import PasswordResetTokenGenerator


class TokenConfirmacaoEmailGenerator(
    PasswordResetTokenGenerator
):

    def _make_hash_value(
        self,
        user,
        timestamp
    ):

        return (
            f'{user.pk}'
            f'{user.password}'
            f'{timestamp}'
            f'{user.email}'
            f'{user.is_active}'
        )


token_confirmacao_email = (
    TokenConfirmacaoEmailGenerator()
)