{% test rollup_reconciles(model, column_name, parent_model, parent_column, group_by) %}

with child as (
    select
        {{ group_by }}           as grain_key,
        sum({{ column_name }})   as child_total
    from {{ model }}
    group by 1
),

parent as (
    select
        {{ group_by }}           as grain_key,
        sum({{ parent_column }}) as parent_total
    from {{ parent_model }}
    group by 1
)

select
    coalesce(child.grain_key, parent.grain_key) as grain_key,
    child.child_total,
    parent.parent_total
from child
full outer join parent on child.grain_key = parent.grain_key
where abs(coalesce(child.child_total, 0) - coalesce(parent.parent_total, 0)) > 0.001

{% endtest %}
