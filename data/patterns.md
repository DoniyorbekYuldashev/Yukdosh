# Domain hints (Central Asian freight). Cities & truck spellings are normalized in code.

is_load = false (EMPTY TRUCK) only for: "bo'sh mashina", "свободная машина", "фура бор",
"mashina bor", "свободен", "пустая". Everything else is a load (true).

Price: "45 mln"/"45 млн" -> 45000000; "1.5 mln" -> 1500000. "kelishilgan"/"договорная"/
"нарх келишамиз" -> price null (negotiable). "tonnasi 500"/"за тонну" = per-ton — capture the number.
Weight: "20000 кг" -> 20 tons (divide by 1000).

A message very often lists MANY loads — extract EVERY direction as its own load, never just the first.
