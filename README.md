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

## 目录结构

```yaml
root:
    -   gap:
            primary_category:
                -   women:
                        sub_category:
                            -   default:
                                    -   product:
                                            product_data: product.json
                                            review_data: review.json
                                            raw_data:
                                                raw_content: raw.json
                                            image_url: image.jpg
                                            model_image_url: model.jpg
                                            model_image_urls:
                                                - model-01.jpg
                                                - model-02.jpg
                                            sku:
                                                sku_data: sku.json
                                                model:
                                                    - image.jpg
                                                    - image.jpg
                                                    -   dresses:
                                    -   product2:
                                            product_data: product.json
                                            review_data: review.json
                                            raw_data:
                                                raw_content: raw.json
                                            image_url: image.jpg
                                            model_image_url: model.jpg
                                            model_image_urls:
                                                - model-01.jpg
                                                - model-02.jpg
                                            sku:
                                                sku_data: sku.json
                                                model:
                                                    - image.jpg
                                                    - image.jpg
                    raw:
                -   men:
                -   girls:
                -   boys:
    #            reviews:
    #            contents:
    #            apis:
    -   target:
    -   next:
    -   jcpenney:
    -   amazon:


```

## codegen

```shell

playwright codegen https://filatz.tmall.com/category-1579712545.htm\?catId\=1579712545\&orderType\=hotsell_desc  -o demo.py -b chromium


```