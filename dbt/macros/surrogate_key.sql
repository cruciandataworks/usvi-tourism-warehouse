-- A stable id built from the columns that make a row unique (a hash of their values).
{% macro dbt_utils_surrogate_key(cols) -%}
    md5(concat_ws('|', {% for c in cols %}cast({{ c }} as varchar){% if not loop.last %}, {% endif %}{% endfor %}))
{%- endmacro %}
