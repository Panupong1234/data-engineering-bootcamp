select
    user_guid,
    created_at_utc,
    updated_at_utc

from {{ ref('stg_greenery__users') }}
where updated_at_utc < created_at_utc
