from pathlib import Path
from typing import Type, Tuple

from pydantic import BaseModel, computed_field, MySQLDsn, DirectoryPath
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
)

from crawler import log


class MySQL(BaseModel):
    host: str
    user: str
    password: str
    db: str
    port: int


class MySQLMoLook(MySQL):
    db2: str


class Aliyun(BaseModel):
    end_point: str
    access_key: str
    secret_key: str
    bucket_name: str
    domain: str
    ...


class Redis(BaseModel):
    host: str
    port: int
    db: int | None = None
    password: str | None = None


class PlayWright(BaseModel):
    timeout: int = 1000 * 60 * 5
    concurrency: int = 10
    headless: bool = True


class Settings(BaseSettings):
    mysql: MySQL
    molook_db: MySQLMoLook
    playwright: PlayWright
    httpx_timeout: int = 60
    save_login_state: bool = True  # 保存登录状态
    base_dir: DirectoryPath | str = Path(__file__).resolve().parent
    project_dir: DirectoryPath | str = base_dir.parent
    data_dir: DirectoryPath | str = Path.home().joinpath("crawler")
    user_data_dir: DirectoryPath | str = project_dir.joinpath("browser_data")
    aliyun: Aliyun
    redis: Redis

    # @computed_field
    # def base_dir(self) -> DirectoryPath:
    #     return Path(__file__).resolve().parent
    #
    # @computed_field
    # def project_dir(self) -> DirectoryPath:
    #     return self.base_dir.parent

    @computed_field
    def mysql_dsn(self) -> MySQLDsn:
        ...
        return f"mysql+mysqlconnector://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.db}"

    @computed_field
    def redis_dsn(self) -> str:
        return f"redis://:{self.redis.password}@{self.redis.host}:{self.redis.port}/{self.redis.db}"

    @computed_field
    def molook_db2_dsn(self) -> MySQLDsn:
        return f"mysql+mysqlconnector://{self.molook_db.user}:{self.molook_db.password}@{self.molook_db.host}:{self.molook_db.port}/{self.molook_db.db2}"

    @computed_field
    def molook_db_dsn(self) -> MySQLDsn:
        return f"mysql+mysqlconnector://{self.molook_db.user}:{self.molook_db.password}@{self.molook_db.host}:{self.molook_db.port}/{self.molook_db.db}"

    model_config = SettingsConfigDict(
        yaml_file=[
            "config.yml",
            "config.local.yml",
            "config.dev.local.yml",
            "config.staging.yml",
            "config.prod.yml",
        ],
        env_file=[".env", ".env.local", ".env.staging", ".env.prod"],
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    pass


settings = Settings()

if __name__ == "__main__":
    log.info(settings)
    log.info(settings.mysql_dsn)
    log.info(settings.base_dir)
    log.info(settings.project_dir)
    log.info(settings.data_dir)
    log.info(settings.aliyun)
    log.info(settings.redis)
    log.info(settings.redis_dsn)
