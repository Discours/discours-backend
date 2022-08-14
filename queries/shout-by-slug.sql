SELECT s.*, a.*, sa.* FROM shout s 
JOIN shout_author sa ON s.slug = sa.shout 
JOIN user a ON a.slug = sa.user 
WHERE sa.slug = a.slug AND a.slug = %s;