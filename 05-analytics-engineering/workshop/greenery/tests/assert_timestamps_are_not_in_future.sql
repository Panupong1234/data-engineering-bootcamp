select
    user_id,
    created_at,
    updated_at

from {{ ref('my_users') }}
where created_at > current_timestamp()
   or updated_at > current_timestamp()
