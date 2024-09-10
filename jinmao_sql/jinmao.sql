select count(*)
from product_sku;
select count(*)
from product_sku;
select count(*)
from product_review;
select source, count(*)
from product
group by source;
select source, count(*)
from product_sku
group by source;
select source, count(*)
from product_review
group by source;

select *
from product_review
where review_id = 'ec5f7814-3d03-4b2c-af09-4edf36802c7f';

# 检查商品抓取状态
select product.product_id, category, gender, sub_category, main_category, product.source
from product_detail,
     product
where product.product_id = product_detail.product_id
  and gender = 'women'
  and sub_category = 'shorts'
  and product.source = 'target';
select category, gender, main_category, sub_category, product.source
from product_detail,
     product
where product.product_id = product_detail.product_id
  and sub_category = 'pets'
  and product.source = 'next';

# 获取索引pdp
select product.product_id, product.primary_sku_id, main_category, sub_category, gender, product.source
from product_detail
         LEFT JOIN
     product on product.product_id = product_detail.product_id and product.source = product_detail.source
where product.product_id = 'ST297321';
select *
from product_d
where product_id = 'ST297321';
# 获取PDP 详情
select product_sku.product_id, product_sku.sku_id, main_category, sub_category, product_sku.source, model_image_urls
from product_sku
         LEFT JOIN
     product_detail on product_sku.product_id = product_detail.product_id and product_sku.source = product_detail.source
where product_sku.source = 'next';

select product.product_id, product.primary_sku_id, main_category, sub_category, product.source, product.product_name
from product
         LEFT JOIN
     product_detail on product.product_id = product_detail.product_id and product.source = product_detail.source
where product.source = 'next'
  and product_name like '%jama%'
  and main_category in ('women');

select product.product_id,
       product.primary_sku_id,
       product.source,
       product.product_name,
       gender,
       main_category,
       sub_category,
       category
from product_sku
         LEFT JOIN
     product on product_sku.product_id = product.product_id and product_sku.source = product.source
         INNER JOIN product_detail
                    on product.product_id = product_detail.product_id and product.source = product_detail.source
where product.source = 'next'
  and product_name like '%jama%'
  and gender in ('men');

# 获取各子类sku数量
select main_category, sub_category, product_sku.source, count(*) as count
from product_sku
         LEFT JOIN
     product_detail on product_sku.product_id = product_detail.product_id and product_sku.source = product_detail.source
where product_sku.source = 'next'
group by main_category, sub_category, product_sku.source
order by count desc;

# 获取各主类类sku数量
select main_category, product_sku.source, count(*) as count
from product_sku
         LEFT JOIN
     product_detail on product_sku.product_id = product_detail.product_id and product_sku.source = product_detail.source
where product_sku.source = 'jcpenney'
group by main_category, product_sku.source
order by count desc;


select count(*)
from product_sku
where source = 'jcpenney'
  and model_image_urls is null;

# sku 按product_id 分组
select product_id, count(*) as count
from product_sku
where source = 'jcpenney'
group by product_id
order by count desc;

select *
from product_sku
where product_id = 'ppr5008179262';

update product_detail
set main_category = 'girls'
where source = 'next'
  and main_category = 'unisex';

select *
from product_detail
where product_id = 'ST297321';



select source, gender, count(*) as count
from product
where source = 'jcpenney'
group by gender
order by count desc;

select count(*)
from product_detail
where source = 'target'
  and main_category is not null;

select product_sku.product_id, sku_id, product_url
from product_sku
where sku_id = 'Q73818';
select sku_id, source, product_id, product_url
from product_sku
where sku_id = 'E31877';
select *
from product_sku
where sku_id = 'q73818';

select *
from product_detail
where source = 'next'
order by id desc;



select sku_id, count(*) as count
from product_sku
where source = 'next'
group by sku_id
order by count desc;

select *
from product_detail
where product_id = 'SU159546';

select count(*)
from product_review;

select *
from product_sku
where product_id in (select product_id from product_detail where source = 'target' and sub_category = 'pants')
;


select *
from product
where source = 'next'
order by created_at desc;

update product
set created_at = gathered_at,
    updated_at = last_gathered_at
where source = 'gap';
update product_review
set created_at = gathered_at,
    updated_at = last_gathered_at
where source = 'gap';
update product_sku
set created_at = gathered_at,
    updated_at = last_gathered_at
where source = 'gap';

UPDATE product_detail pd
    JOIN product p ON pd.product_id = p.product_id AND pd.source = p.source
SET pd.main_category = p.gender
WHERE pd.product_id = p.product_id
  AND pd.source = p.source;


select *
from product
where category is null
  and source = 'jcpenney';

select *
from product
where source = 'jcpenney';


select count(*)
from product_review;

select product_id
from product
where source = 'gap'
  and id >= 46000
order by id desc;

select *
from product
where product_id = '80783370';


select *
from product
where source = 'target'
  and tags is not null;

select id, product_id, released_at
from product
where source = 'target'
order by id desc;

select distinct product.gender
from product;

select *
from product
where gender = 'default';

update product
set gender = 'unknown'
where gender = 'O';

select *
from product
where gender is null;


select *
from product
         join product_detail on product.product_id = product_detail.product_id
where product.product_id = '76375257';

select *
from product_sku
where source = 'jcpenney';

# update product_sku set outer_model_image_urls = model_image_urls where source = 'jcpenney';

select *
from product_sku
where product_id = '709290';


select *
from product_sku
where source = 'gap'
order by id desc;
select *
from product_detail
where product_id = '874579';

show index from product_review;


select *
from product_sku
where source = 'jcpenney'
order by id desc;


select category, category_id
from product
where source = 'target';
select *
from product
where source = 'jcpenney'
order by id desc;


select *
from product
where source = 'jcpenney'
  and gender = 'men';

# update product_sku set outer_model_image_urls = model_image_urls where source = 'jcpenney';

show status;

SHOW VARIABLES LIKE 'max_connections';
SHOW STATUS LIKE 'Threads_connected';
SET GLOBAL max_connections = 500;

select product_id
from product_detail
where source = 'jcpenney'
  and main_category = 'jewelry-and-watches';


select *
from product
where category = 'Pets'
  and source = 'next'
  and gender != 'unisex';

update product
set gender = 'unisex'
where category = 'Pets'
  and source = 'next'
  and gender = 'women';

select *
from product
where product_id = 'st130964';


select *
from product_detail
where main_category = 'default';

select *
from product
         join crawler.product_detail pd on product.id = pd.id
where main_category is null
  and pd.source = 'next';

select *
from product_detail
where main_category is null
  and source = 'next';



select *
from product
where created_at >= '2024-09-01'
  and source = 'next'
order by created_at desc;