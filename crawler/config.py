from pathlib import Path
from typing import Type, Tuple

from pydantic import BaseModel, computed_field, MySQLDsn, AnyHttpUrl, field_validator, field_serializer
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


class LLM(BaseModel):
    api_key: str
    base_url: str
    model: str


class Redis(BaseModel):
    host: str
    port: int
    db: int | None = None
    password: str | None = None


class PlayWright(BaseModel):
    timeout: int = 1000 * 60 * 5
    concurrency: int = 10
    headless: bool = True


class HTTPX(BaseModel):
    timeout: int = 60
    proxy_url: str | None = None


class ProxyPool(BaseModel):
    status: bool = False
    server: str | None = None
    username: str | None = None
    password: str | None = None


class Settings(BaseSettings):
    mysql: MySQL
    mysql_test: MySQL  # 测试数据库
    molook_db: MySQLMoLook
    playwright: PlayWright
    httpx_timeout: int = 180
    review_analysis_concurrency: int = 500
    proxy_url: AnyHttpUrl | str
    proxy_pool: ProxyPool
    save_login_state: bool = True  # 保存登录状态
    base_dir: Path | str = Path(__file__).resolve().parent
    project_dir: Path | str = base_dir.parent
    log_file_path: str | Path = project_dir.joinpath("logs")
    data_dir: Path | str = Path.home().joinpath("crawler")
    cong_dir: Path | str = Path.home().joinpath("congcong")
    user_data_dir: Path | str = project_dir.joinpath("browser_data")
    aliyun: Aliyun
    redis: Redis
    ark_doubao: LLM
    glm4_air: LLM
    claude_haiku: LLM
    # ark_api_key: str  # 豆包api-key
    # ark_base_url: str  # 豆包api-url
    ark_prompt: str  # 评论分析Prompt
    ark_summary_prompt: str  # 评论总结Prompt
    ark_extra_metrics_prompt: str  # 额外指标分析提示词
    # ark_model: str
    ark_concurrency: int = 40
    translate_prompt: str  # 翻译Prompt

    @field_serializer("proxy_url", when_used="always")
    def proxy_url_serializer(self, proxy_url: AnyHttpUrl) -> str:
        return str(proxy_url)

    @classmethod
    @field_validator("proxy_url", mode="after")
    def proxy_url_validator(cls, proxy_url: AnyHttpUrl) -> str:
        return str(proxy_url)

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
        return f"mysql+pymysql://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.db}"
        # return f"mysql+mysqldb://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.db}"

    @computed_field
    def mysql_async_dsn(self) -> MySQLDsn:
        ...
        return f"mysql+aiomysql://{self.mysql.user}:{self.mysql.password}@{self.mysql.host}:{self.mysql.port}/{self.mysql.db}"

    @computed_field
    def mysql_test_async_dsn(self) -> MySQLDsn:
        ...
        return f"mysql+aiomysql://{self.mysql_test.user}:{self.mysql_test.password}@{self.mysql_test.host}:{self.mysql_test.port}/{self.mysql_test.db}"

    @computed_field
    def mysql_test_dsn(self) -> MySQLDsn:
        ...
        return f"mysql+pymysql://{self.mysql_test.user}:{self.mysql_test.password}@{self.mysql_test.host}:{self.mysql_test.port}/{self.mysql_test.db}"

    @computed_field
    def redis_dsn(self) -> str:
        return f"redis://:{self.redis.password}@{self.redis.host}:{self.redis.port}/{self.redis.db}"

    @computed_field
    def molook_db2_dsn(self) -> MySQLDsn:
        return f"mysql+pymysql://{self.molook_db.user}:{self.molook_db.password}@{self.molook_db.host}:{self.molook_db.port}/{self.molook_db.db2}"

    @computed_field
    def molook_db_dsn(self) -> MySQLDsn:
        return f"mysql+pymysql://{self.molook_db.user}:{self.molook_db.password}@{self.molook_db.host}:{self.molook_db.port}/{self.molook_db.db}"

    model_config = SettingsConfigDict(
        yaml_file=[
            "config.yml",
            "config.dev.yml",
            "config.staging.yml",
            "config.prod.yml",
            "config.local.yml",
            "config.dev.local.yml",
            "config.staging.local.yml",
            "config.prod.local.yml",
        ],
        yaml_file_encoding="utf-8",
        env_file=[
            ".env", ".env.dev", ".env.staging", ".env.prod", ".env.local", ".env.dev.local", ".env.staging.local",
            ".env.prod.local"
        ],
        env_file_encoding="utf-8",
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
    log.info(settings.mysql_test_async_dsn)
    log.info(settings.base_dir)
    log.info(settings.project_dir)
    # log.info(settings.log_file_path)
    log.info(f"{settings.data_dir=}")
    log.info(settings.aliyun)
    log.info(settings.redis)
    log.info(settings.redis_dsn)
    # log.info(settings.ark_api_key)
    # log.info(f"type:{type(settings.proxy_url)}, value:{settings.proxy_url}")
    # log.info(settings.ark_extra_metrics_prompt)
    # log.info(settings.ark_prompt)
    # log.info(settings.proxy_pool)
