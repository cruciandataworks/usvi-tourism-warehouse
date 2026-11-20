-- Fails for any combination of columns that appears more than once.
{% test dbt_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

-- Fails (or warns) for any row matching a condition.
{% test assert_no_rows_where(model, condition) %}
select * from {{ model }} where {{ condition }}
{% endtest %}
