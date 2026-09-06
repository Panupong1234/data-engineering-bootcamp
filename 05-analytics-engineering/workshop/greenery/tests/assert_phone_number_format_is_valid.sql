select
    phone_number

from {{ ref('my_users') }}
where not regexp_contains(phone_number, r'^[0-9]{3}-[0-9]{3}-[0-9]{4}$')
