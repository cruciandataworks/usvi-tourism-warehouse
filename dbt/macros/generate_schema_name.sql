-- By default dbt names schemas "main_staging". This keeps them simply "staging", "marts".
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
