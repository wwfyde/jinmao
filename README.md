# Crawler
> MoLook scraping&crawling scripts. 
## Links
- https://playwright.dev
- https://playwright.dev/python/
- [爬虫参考](https://github.com/NanmiCoder/MediaCrawler)

### 目标网站

- https://www.tmall.com
- https://www.jd.com
- https://www.taobao.com
- https://www.1688.com
- https://www.gap.com
- https://us.burberry.com
- https://target.com
- https://www.amazon.com
- https://jcpenny.com
- https://next.co.uk

## 代理-Proxy

> [!tip]
>
> 智能代理

https://www.jisuhttp.com
https://fineproxy.org/cn/websites/target-com/
https://proxyelite.info/cn/websites/target-com/


## Features

- 支持保存数据到csv/json
- 支持保存数据到数据库

## playwright

```shell
# 安装 可用浏览器
playwright install
```


## tips

- 通过 chrome dev tools -元素(element) 右键节点可以复制各种风格的选择器
- 自己写代码


## codegen

```shell

playwright codegen https://filatz.tmall.com/category-1579712545.htm\?catId\=1579712545\&orderType\=hotsell_desc  -o demo.py -b chromium


```