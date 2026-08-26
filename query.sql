set search_path to olist;

-- Q2
select c.customer_state,eng.product_category_name_english,AVG(pay.payment_value) as average_order_value
from orders as o
join customers as c on c.customer_id=o.customer_id
join order_payments as pay  on pay.order_id=o.order_id
join order_items as itm on o.order_id =itm.order_id
join products as p on p.product_id=itm.product_id
join product_category_name_translation as eng on eng.product_category_name=p.product_category_name
where o.order_status='delivered'
group by c.customer_state,eng.product_category_name
order by AVG(pay.payment_value) desc;

--Q3
select eng.product_category_name_english as product_category , sum(pay.payment_value) as revenue
from orders as o 
join order_payments as pay  on pay.order_id=o.order_id
join order_items as itm on o.order_id =itm.order_id
join products as p on p.product_id=itm.product_id
join product_category_name_translation as eng on eng.product_category_name=p.product_category_name
where o.order_status='delivered'
group by product_category
order by revenue desc
limit 10 

--Q9
-- avg review score
select c.customer_state,eng.product_category_name_english as product_category ,AVG(rev.review_score) as average_review_score
from orders as o
join customers as c on c.customer_id=o.customer_id
join order_reviews as rev  on rev.order_id=o.order_id
join order_items as itm on o.order_id =itm.order_id
join products as p on p.product_id=itm.product_id
join product_category_name_translation as eng on eng.product_category_name=p.product_category_name
where o.order_status='delivered'
group by c.customer_state,product_category;


--Q4
select eng.product_category_name_english as product_category,
	AVG(
		ROUND(
			(ot.freight_value/ot.price)*100
		,2)
	) as Average_percentage_freight_value
from order_items as ot
join products as p on ot.product_id=p.product_id
join product_category_name_translation as eng on eng.product_category_name=p.product_category_name
group by product_category
order by Average_percentage_freight_value desc;

--Q5

select 
    payment_type,
	CASE
		WHEN payment_installments=1 THEN 'full payment'
		ELSE 'on installment'
 	END AS Payment_installment,
	
 	sum(payment_value) as revenue 
from order_payments as op
group by payment_type,
	CASE
	WHEN payment_installments=1 THEN 'full payment'
	ELSE 'on installment'
	END
having sum(payment_value)>0;


--Q6
select 
	EXTRACT(HOURS FROM o.ORDER_PURCHASE_TIMESTAMP) as hour_of_the_day,
	TO_CHAR(o.ORDER_PURCHASE_TIMESTAMP,'Day') as Day_of_week, 
	count(o.order_id) as number_of_orders
from orders as o 
where o.order_status='delivered'
group by EXTRACT(HOURS FROM o.ORDER_PURCHASE_TIMESTAMP),TO_CHAR(o.ORDER_PURCHASE_TIMESTAMP,'Day')
order by number_of_orders desc;

--Q8
select customer_id, count(order_id) as no_of_orders
from orders as o 
where order_status='delivered'
group by customer_id
having (count(order_id)>1);


--Does late delivery explain low scores? Category avg score split by on-time vs late

with delivery_delay as (
select o.order_id,
	CASE 
	WHEN o.order_delivered_customer_date<=o.order_estimated_delivery_date THEN 'on_time' 
	ELSE 'delayed'
	END as  delivery_delay_status
from orders as o
where o.order_delivered_customer_date iS NOT NULL AND o.order_estimated_delivery_date is NOT NULL
)
,review_score as(
	select 
		eng.product_category_name_english as category,
		dd.delivery_delay_status ,
		COUNT(ore.review_id) as review_count,
		AVG(ore.review_score) as avg_review_score 
	
	from order_reviews as ore
	NATURAL JOIN delivery_delay as dd
	join order_items as oi on oi.order_id=ore.order_id
	join products as p on  oi.product_id=p.product_id
	join product_category_name_translation as eng on eng.product_category_name=p.product_category_name
	
	group by eng.product_category_name_english,dd.delivery_delay_status
	HAVING    COUNT(ore.review_id) >= 30
	)

select category , delivery_delay_status , review_count , ROUND(avg_review_score,2) as avg_review,
		ROUND(AVG(
		CASE 
		WHEN delivery_delay_status ='on_time'
		THEN avg_review_score
		END ) OVER(PARTITION BY category)
		- AVG(
		CASE 
		WHEN delivery_delay_status ='delayed' 
		THEN avg_review_score 
		END ) OVER(PARTITION BY category),2) as score_difference
		
	
from review_score;


--25
WITH seller_category_sales AS (

    SELECT
        oi.seller_id,

        eng.product_category_name_english AS category,

        SUM(oi.price) AS category_revenue

    FROM order_items oi

    JOIN products p
        ON oi.product_id = p.product_id

    JOIN product_category_name_translation eng
        ON eng.product_category_name = p.product_category_name

    GROUP BY
        oi.seller_id,
        eng.product_category_name_english
),

seller_total_sales AS (

    SELECT
        seller_id,
        SUM(category_revenue) AS total_revenue

    FROM seller_category_sales

    GROUP BY seller_id
),

specialization AS (

    SELECT
        scs.seller_id,
        scs.category,
        scs.category_revenue,
        sts.total_revenue,

        ROUND(
            (scs.category_revenue / sts.total_revenue) * 100,
            2
        ) AS category_contribution_pct,

        RANK() OVER(
            PARTITION BY scs.seller_id
            ORDER BY scs.category_revenue DESC
        ) AS category_rank

    FROM seller_category_sales scs

    JOIN seller_total_sales sts
        ON scs.seller_id = sts.seller_id
)

SELECT
    seller_id,
    category AS dominant_category,
    category_revenue,
    total_revenue,
    category_contribution_pct

FROM specialization

WHERE category_rank = 1
  AND category_contribution_pct >= 70

ORDER BY category_contribution_pct DESC;


--Write the SQL query for: Monthly GMV trend — total payment value by order month with MoM growth %

WITH MONTHLY_GMV AS (
SELECT 
	DATE_TRUNC('month',O.ORDER_PURCHASE_TIMESTAMP) AS ORDER_MONTH,
	ROUND(SUM(OP.PAYMENT_VALUE),2) AS TOTAL_MONTHLY_GMV
FROM ORDER_PAYMENTS AS OP
JOIN ORDERS AS O ON OP.ORDER_ID=O.ORDER_ID 
WHERE O.ORDER_STATUS='delivered'
GROUP BY ORDER_MONTH), 

GMV_GROWTH AS (
SELECT 
	ORDER_MONTH,
	TOTAL_MONTHLY_GMV,
	LAG(TOTAL_MONTHLY_GMV) OVER(ORDER BY ORDER_MONTH) AS PREVIOUS_MONTH_GMV
FROM MONTHLY_GMV
)


SELECT 
	ORDER_MONTH,
	ROUND(
		((TOTAL_MONTHLY_GMV-PREVIOUS_MONTH_GMV) /PREVIOUS_MONTH_GMV)*100 
		,2) AS GMV_PERCENTAGE_GROWTH
FROM GMV_GROWTH 
ORDER BY ORDER_MONTH
OFFSET 2;

-- 
SELECT ENG.PRODUCT_CATEGORY_NAME_ENGLISH AS PRODUCT_CATEGORY_NAME,
	DATE_TRUNC('month',O.ORDER_PURCHASE_TIMESTAMP) AS ORDER_MONTH,
	ROUND(
	COUNT(CASE WHEN O.ORDER_STATUS!='delivered' THEN O.ORDER_ID END)/
	COUNT(O.ORDER_ID) ,2) * 100 AS ORDER_CANCELLATION_RATE
FROM ORDERS AS O 
JOIN ORDER_ITEMS AS OI ON O.ORDER_ID=OI.ORDER_ID 
JOIN PRODUCTS AS P ON OI.PRODUCT_ID=P.PRODUCT_ID
JOIN PRODUCT_CATEGORY_NAME_TRANSLATION AS ENG ON ENG.PRODUCT_CATEGORY_NAME=P.PRODUCT_CATEGORY_NAME

GROUP BY ENG.PRODUCT_CATEGORY_NAME_ENGLISH ,DATE_TRUNC('month',O.ORDER_PURCHASE_TIMESTAMP)
ORDER BY ORDER_CANCELLATION_RATE DESC;


---





