"""Провайдер настроек приложения."""

from dishka import Provider, Scope, provide

from app.config.settings import Settings


class SettingsProvider(Provider):
    """Отдаёт глобальный экземпляр Settings как синглтон."""

    @provide(scope=Scope.APP)
    def provide_settings(self) -> Settings:
        return Settings()
