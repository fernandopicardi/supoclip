-- Additive metadata only; preserve every existing preference and account.
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "default_caption_style" JSONB NOT NULL DEFAULT '{}';
