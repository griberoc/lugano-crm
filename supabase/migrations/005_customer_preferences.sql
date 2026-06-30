alter table public.profiles
add column if not exists preferences jsonb not null default '{
  "preferred_contact": null,
  "favorite_categories": [],
  "dietary_restrictions": [],
  "accepts_promotions": true,
  "accepts_whatsapp": true,
  "notes": null
}'::jsonb;
