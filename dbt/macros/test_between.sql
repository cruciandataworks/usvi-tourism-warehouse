-- A reusable test: fails for any row where the column is outside [min_value, max_value].
{% test dbt_expect_between(model, column_name, min_value, max_value) %}
select * from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}
