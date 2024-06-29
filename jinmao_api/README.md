# 部署方式

## 临时启动

```shell
source venv/bin/activate

# 注意工作目录
nohup uvicorn jinmao_api.main:app --host 0.0.0.0 --port 7003 --ssl-keyfile agent.molook.cn.key --ssl-certfile agent.molook.cn.pem > demo.log 2>&1 &
```

## 使用docker

## 接口需求

### 额外指标分析

从数据库拿取上次指标分析的列表, 最多3个, 存取指标名称

