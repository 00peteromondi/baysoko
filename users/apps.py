from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Avoid performing DB queries during AppConfig.ready (import-time).
        # Instead, register a post_migrate handler that will create/update
        # SocialApp entries after migrations have run. This prevents the
        # RuntimeWarning about accessing the DB during app initialization
        # and is safer for tests/CI where migrations are run programmatically.
        try:
            from django.db.models.signals import post_migrate
            import os

            def _ensure_social_apps(sender, **kwargs):
                try:
                    from django.contrib.sites.models import Site
                    from allauth.socialaccount.models import SocialApp

                    site = Site.objects.get_current()

                    # Allow overriding site domain via environment variable
                    site_domain = os.environ.get('SITE_DOMAIN') or os.environ.get('RENDER_EXTERNAL_HOSTNAME')
                    if site_domain:
                        site.domain = site_domain
                        site.name = os.environ.get('SITE_NAME', site.name or 'Baysoko')
                        site.save()

                    def ensure_social_app(provider, client_env, secret_env, display_name):
                        client_id = os.environ.get(client_env)
                        secret = os.environ.get(secret_env)
                        if client_id and secret:
                            app, created = SocialApp.objects.update_or_create(
                                provider=provider,
                                defaults={
                                    'name': display_name,
                                    'client_id': client_id,
                                    'secret': secret,
                                }
                            )
                            app.sites.add(site)

                    ensure_social_app(
                        'google',
                        'GOOGLE_OAUTH_CLIENT_ID',
                        'GOOGLE_OAUTH_CLIENT_SECRET',
                        'Google',
                    )
                    ensure_social_app(
                        'facebook',
                        'FACEBOOK_OAUTH_CLIENT_ID',
                        'FACEBOOK_OAUTH_CLIENT_SECRET',
                        'Facebook',
                    )

                except Exception:
                    # Intentionally silent: we don't want social app creation to
                    # break migrations or other management commands.
                    return

            post_migrate.connect(_ensure_social_apps, dispatch_uid='users.ensure_social_apps')
        except Exception:
            # If signals can't be imported for any reason (very unlikely),
            # just skip the initialization; it's non-critical.
            pass