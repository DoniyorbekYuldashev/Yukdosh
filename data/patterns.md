# FIELD RULES (highest priority)
- Default is_load = TRUE (it's a load). Only FALSE for empty-truck offers: "bo'sh mashina",
  "fura bor", "mashina bor", "свободная машина", "свободен", "пустая".
- origin (From) and destination (Destination) are almost always BOTH present. First city = origin,
  second = destination. Never leave origin empty when a route exists.
- truck_type = vehicle type ONLY (tent/ref/isotherm/flatbed/container/dump). Words тент/фура/реф/
  борт/контейнер are truck_type, NEVER cargo.
- cargo_type = what the goods ARE (metal, paxta, meva, steklovata, масло). Never a truck word.
- Put everything else in comment; lose nothing.
- Each 'A-B' direction = one load (A=origin, B=destination). Several directions = several loads. Same origin, different destinations stays SEPARATE — never merge cities across loads (shared origin, multiple destinations).

# Sarbon parsing patterns (Central Asian freight Telegram posts)

These notes are fed to the model as priority guidance. Add real patterns you see in
your groups. Order = priority (most important first).

## Load vs empty truck (is_load)
- LOAD (is_load=true) — someone HAS cargo: "yuk bor", "груз есть", "юк бор", "gruz bor",
  "yuk chiqdi", "требуется машина", "mashina kerak", "фура керак".
- EMPTY TRUCK (is_load=false) — someone HAS a free truck: "bo'sh mashina", "бўш машина",
  "свободная машина", "фура бор", "mashina bor", "boш", "свободен", "пустой".

## Route (origin -> destination)
- Usually "A - B", "A—B", "A/B", "A dan B ga", "Адан Бгача", "A→B".
- First city = origin, second = destination.
- International: "халқаро", "xalqaro", country names (Rossiya, Qozogʻiston, Turkiya).

## Cities (canonical -> variants seen)
- Toshkent: Тошкент, Tashkent, Ташкент, Tosh, Тош, TSH
- Samarqand: Самарканд, Samarkand, Смк
- Buxoro: Бухоро, Bukhara, Бухара
- Andijon, Namangan, Fargʻona (Фаргона), Qoʻqon (Коканд)
- Qarshi, Termiz, Nukus, Urganch (Ургенч), Xiva (Хива)
- Moskva (Москва), Sankt-Peterburg (Питер, СПб), Almaty (Алматы), Nur-Sultan/Astana

## Truck types (truck_type)
- tent: тент, фура, tent, ten
- ref: реф, рефрижератор, refrijerator, холодильник
- isotherm: изотерм, izoterm
- flatbed: борт, бортовой, площадка, bortli, ochiq (open)
- container: контейнер, konteyner
- dump: самосвал, samosval
- also: "mega", "стандарт", "20 тонник", "90 куб" (size hints — put cubic in volume_m3)

## Weight & volume
- weight_tons: "20т", "20 тонна", "20 тн", "20000 кг" (÷1000 -> tons)
- volume_m3: "90 куб", "86 m3", "90 кубов"

## Price (price_amount + price_currency)
- "45 mln" / "45 млн" -> 45000000 ; "1.5 mln" -> 1500000
- currency: сум/so'm -> UZS; руб -> RUB; тенге -> KZT; $/usd/доллар -> USD
- "kelishilgan", "договорная", "нарх келишамиз" -> price_amount null (negotiable)
- "tonnasi 500", "за тонну" -> per-ton price (still capture the number)

## Contact
- One or MANY phones may appear; capture all (comma-separated). Formats: +998 90 123 45 67,
  90-123-45-67, 998901234567. Also Telegram @usernames may be the contact.

## Multi-load posts
- One message may list several loads. Extract the FIRST/primary load; if clearly separate
  loads, they can be split, but prefer the main one.

## Noise to ignore
- Ads, "reklama", channel promos, greetings, stickers, prices of unrelated goods.
