select *
from product
         inner join product_detail on product.product_id = product_detail.product_id
where product.product_id = 'ST156684';

select *
from product
where created_at >= '2024-08-30'
  and source = 'next' order by created_at desc;


select *


select *
from product_sku
where source = 'other';