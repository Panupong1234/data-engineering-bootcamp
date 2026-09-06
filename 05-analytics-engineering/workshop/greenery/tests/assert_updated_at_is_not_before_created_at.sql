select
    user_id,
    created_at,
    updated_at

from {{ ref('my_users') }}
where updated_at < created_at
