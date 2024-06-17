# 金茂

商品评论582943 图片抓取失败

#  

- https://www.gap.com/

- https://www.jcpenney.com/

- https://www.target.com/
- https://www.next.co.uk/

## 数据结构

关于主图:  > products > styleId > styleColors > images > Z
反面图:  > products > styleId > styleColors > images > AV1_Z

## 问题记录

- [0525], 当加载到第36个后, 第37个获取定位器失败
- [0525], 处理分页问题, 需要继续读取
- [0527], 打分数和评论数不一致

## 开发日志

- 分页处理
- 图片下载

### 图片爬取

向量化, 近似度, 相似度搜索, 向量搜索

流程跑通

### 评论爬取

## gap

```shell

#\38 90844002 > a
#\38 90844002 > a
#search-page > div > div > div > div.css-1vggvlj > div.css-157ddu3 > div.css-17e2vw5 > div > div
#search-page > div > div > div > div.css-15k4xi > div > div.css-17e2vw5 > div > div
#search-page > div > div > div > div.search-page__product-grid.css-1xlfwl6 > section > div > div:nth-child(2)
```

## 重点API

### 类别

https://api.gap.com/commerce/search/products/v2/cc?brand=gap&market=us&cid=14417&locale=en_US&pageSize=300&ignoreInventory=false&includeMarketingFlagsDetails=true&pageNumber=0&department=48&vendor=Certona

### 评论

- https://display.powerreviews.com/m/1443032450/l/en_US/product/540635/reviews?_noconfig=true
- https://display.powerreviews.com/m/1443032450/l/en_US/product/540635/reviews?paging.from=10&paging.size=10&filters=&search=&sort=Newest&image_only=false&page_locale=en_US&_noconfig=true
- https://display.powerreviews.com/m/1443032450/l/en_US/product/540635/reviews?paging.from=20&paging.size=10&filters=&search=&sort=Newest&image_only=false&page_locale=en_US&_noconfig=true

### 商品API

- [0524]
- https://www.gap.com/browse/product.do?pid=540635032&vid=1&searchText=T-shirt#pdp-page-content

## API

API Request
URL: https://api.gap.com/commerce/search/products/v2/cc?brand=gap&market=us&cid=14417&locale=en_US&pageSize=300&ignoreInventory=false&includeMarketingFlagsDetails=true&pageNumber=0&department=48&vendor=Certona
