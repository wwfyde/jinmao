# 部署方式

## 临时启动

```shell
source venv/bin/activate

# 注意工作目录
nohup uvicorn api.main:app --host 0.0.0.0 --port 7003 --ssl-keyfile agent.molook.cn.key --ssl-certfile agent.molook.cn.pem > demo.log 2>&1 &
```

## 使用docker