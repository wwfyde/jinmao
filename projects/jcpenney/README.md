# 新版本开发

## 流程(新-20240819)

1. `projects\jcpenney\category.py` 获取类别列表
2. `projects\jcpenney\jcpenney_category.py` 将类别加入到商品索引 url
3. `projects\jcpenney\jcpenney_sku.py` 获取商品详情

## 流程(赵轩)

1. `projects\jcpenney\category.py` 获取类别列表，其中内容会有重复
2. `projects\jcpenney\item-list.py` 获取产品列表 url，会用重复产品
3. `projects\jcpenney\jcpenney_sku.py` 获取产品详情

## d

点击按钮

## 问题记录

需要通过分页, 获取商品

## 商品获取

### 按类别

https://www.jcpenney.com/g/women/skirts?id=cat100250097
https://www.jcpenney.com/g/women/skirts?id=cat100250097&page=2&mktTiles=2
https://www.jcpenney.com/g/women/skirts?id=cat100250097&page=3&mktTiles=2
https://www.jcpenney.com/g/women/skirts?id=cat100250097&page=4&mktTiles=2
https://www.jcpenney.com/g/women/skirts?id=cat100250097&page=5&mktTiles=2
https://www.jcpenney.com/g/women/skirts?id=cat100250097&page=6&mktTiles=2

api-1: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&responseType=organic
api-2: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&page=2&mktTiles=2&responseType=organic
api-3: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&page=3&mktTiles=2&responseType=organic
api-4: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&page=4&mktTiles=2&responseType=organic
api-5: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&page=5&mktTiles=2&responseType=organic
api-6: https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&page=6&mktTiles=2&responseType=organic

## 关键参数

sku 只能从 DOM 中获取
product_id 从 url 中取, ppr5008282312
sku_id 从页面取[5620146, 5620147,5620290, 5620289]

## 商品

- https://www.jcpenney.com/p/stafford-coolmax-mens-regular-fit-stretch-fabric-wrinkle-free-long-sleeve-dress-shirt/ppr5008282306?pTmplType=regular&catId=SearchResults&searchTerm=stress&productGridView=medium&badge=onlyatjcp
  https://www.jcpenney.com/p/st-johns-bay-womens-v-neck-short-sleeve-t-shirt/ppr5008403017?pTmplType=regular
  #accordion-button-0

### 5008282306

-https://api.bazaarvoice.com/data/reviews.json?resource=reviews&action=REVIEWS_N_STATS&filter=productid%3Aeq%3Appr5008282306&filter=contentlocale%3Aeq%3Aen_US%2Cen_US&filter=isratingsonly%3Aeq%3Afalse&filter_reviews=contentlocale%3Aeq%3Aen_US%2Cen_US&include=authors%2Cproducts%2Ccomments&filteredstats=reviews&Stats=Reviews&limit=8&offset=0&limit_comments=3&sort=submissiontime%3Adesc&passkey=cajVgXWY2XDAH2N3cUno5xueaAM7EhLaFvcHBnq38TpSI&apiversion=5.5&displaycode=1573-en_us

## 评论 API

- https://api.bazaarvoice.com/data/reviews.json?resource=reviews&action=REVIEWS_N_STATS&filter=productid%3Aeq%3Appr5008403017&filter=contentlocale%3Aeq%3Aen_US%2Cen_US&filter=isratingsonly%3Aeq%3Afalse&filter_reviews=contentlocale%3Aeq%3Aen_US%2Cen_US&include=authors%2Cproducts%2Ccomments&filteredstats=reviews&Stats=Reviews&limit=8&offset=0&limit_comments=3&sort=submissiontime%3Adesc&passkey=cajVgXWY2XDAH2N3cUno5xueaAM7EhLaFvcHBnq38TpSI&apiversion=5.5&displaycode=1573-en_us

- https://api.bazaarvoice.com/data/reviews.json?resource=reviews&action=REVIEWS_N_STATS&filter=productid%3Aeq%3Appr5008403017&filter=contentlocale%3Aeq%3Aen_US%2Cen_US&filter=isratingsonly%3Aeq%3Afalse&filter_reviews=contentlocale%3Aeq%3Aen_US%2Cen_US&include=authors%2Cproducts%2Ccomments&filteredstats=reviews&Stats=Reviews&limit=8&offset=0&limit_comments=3&sort=submissiontime%3Adesc&passkey=cajVgXWY2XDAH2N3cUno5xueaAM7EhLaFvcHBnq38TpSI&apiversion=5.5&displaycode=1573-en_us
