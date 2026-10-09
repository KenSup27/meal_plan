-- Nutrition values are approximate raw-food values per 100g.
-- They are suitable for MVP testing and should be replaceable with a verified source.

insert into public.ingredients
  (
    name,
    category,
    nutrition_basis,
    kcal_per_100g,
    protein_per_100g,
    carbs_per_100g,
    fat_per_100g,
    data_source
  )
values
  ('鸡胸肉', 'meat', 'raw', 133, 23.3, 0.0, 4.7, 'mvp_seed'),
  ('鸡腿肉', 'meat', 'raw', 181, 18.0, 0.0, 12.0, 'mvp_seed'),
  ('瘦猪肉', 'meat', 'raw', 143, 20.3, 1.5, 6.2, 'mvp_seed'),
  ('牛里脊', 'meat', 'raw', 155, 22.0, 0.0, 7.0, 'mvp_seed'),
  ('牛腱子', 'meat', 'raw', 172, 31.0, 0.0, 5.0, 'mvp_seed'),
  ('虾仁', 'seafood', 'raw', 48, 10.0, 0.0, 0.7, 'mvp_seed'),
  ('三文鱼', 'seafood', 'raw', 208, 20.0, 0.0, 13.0, 'mvp_seed'),
  ('鳕鱼', 'seafood', 'raw', 82, 18.0, 0.0, 0.7, 'mvp_seed'),
  ('鸡蛋', 'dairy', 'raw', 144, 12.5, 0.7, 9.5, 'mvp_seed'),
  ('低脂牛奶', 'dairy', 'raw', 46, 3.4, 4.8, 1.5, 'mvp_seed'),
  ('北豆腐', 'dairy', 'raw', 81, 8.1, 4.2, 4.2, 'mvp_seed'),
  ('西兰花', 'vegetable', 'raw', 34, 2.8, 4.3, 0.4, 'mvp_seed'),
  ('菠菜', 'vegetable', 'raw', 23, 2.9, 3.6, 0.4, 'mvp_seed'),
  ('胡萝卜', 'vegetable', 'raw', 41, 0.9, 9.6, 0.2, 'mvp_seed'),
  ('番茄', 'vegetable', 'raw', 18, 0.9, 3.9, 0.2, 'mvp_seed'),
  ('黄瓜', 'vegetable', 'raw', 15, 0.7, 3.6, 0.1, 'mvp_seed'),
  ('彩椒', 'vegetable', 'raw', 31, 1.0, 6.0, 0.3, 'mvp_seed'),
  ('洋葱', 'vegetable', 'raw', 40, 1.1, 9.3, 0.1, 'mvp_seed'),
  ('蘑菇', 'vegetable', 'raw', 22, 3.1, 3.3, 0.3, 'mvp_seed'),
  ('玉米', 'carb', 'raw', 86, 3.3, 19.0, 1.4, 'mvp_seed'),
  ('大米', 'carb', 'raw', 346, 7.4, 77.2, 0.8, 'mvp_seed'),
  ('糙米', 'carb', 'raw', 348, 7.3, 72.0, 2.7, 'mvp_seed'),
  ('燕麦片', 'carb', 'raw', 367, 15.0, 61.0, 6.7, 'mvp_seed'),
  ('全麦面包', 'carb', 'raw', 246, 10.2, 43.0, 4.2, 'mvp_seed'),
  ('意大利面', 'carb', 'raw', 350, 12.5, 72.0, 1.5, 'mvp_seed'),
  ('红薯', 'carb', 'raw', 86, 1.6, 20.1, 0.1, 'mvp_seed'),
  ('土豆', 'carb', 'raw', 77, 2.0, 17.5, 0.1, 'mvp_seed'),
  ('藜麦', 'carb', 'raw', 368, 14.1, 64.2, 6.1, 'mvp_seed'),
  ('香蕉', 'fruit', 'raw', 89, 1.1, 22.8, 0.3, 'mvp_seed'),
  ('苹果', 'fruit', 'raw', 52, 0.3, 13.8, 0.2, 'mvp_seed'),
  ('橄榄油', 'seasoning', 'raw', 884, 0.0, 0.0, 100.0, 'mvp_seed'),
  ('酱油', 'seasoning', 'raw', 53, 8.1, 4.9, 0.1, 'mvp_seed'),
  ('食盐', 'seasoning', 'raw', 0, 0.0, 0.0, 0.0, 'mvp_seed'),
  ('黑胡椒', 'seasoning', 'raw', 251, 10.4, 63.9, 3.3, 'mvp_seed')
on conflict (name) do update set
  category = excluded.category,
  nutrition_basis = excluded.nutrition_basis,
  kcal_per_100g = excluded.kcal_per_100g,
  protein_per_100g = excluded.protein_per_100g,
  carbs_per_100g = excluded.carbs_per_100g,
  fat_per_100g = excluded.fat_per_100g,
  data_source = excluded.data_source,
  is_active = true;
