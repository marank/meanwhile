# Changelog

## 0.1.0 (2026-11-25)


### ⚠ BREAKING CHANGES

* CalDAV no longer accepts the account password, and existing app passwords are removed (only their Argon2 hash was known); users create new ones under the account settings.

### Features

* attach files and links to events, duplicate events, and show them as free or busy ([024d349](https://github.com/marank/meanwhile/commit/024d34938f6a73646fa58b238df138fe88e05980))
* CalDAV signs in with app passwords only, kept as SHA-256 of their token ([e38b7c7](https://github.com/marank/meanwhile/commit/e38b7c7b2a0ed3f1595d5d3fbc671c47dfd87793))
* let each user choose when their day starts ([f0659a0](https://github.com/marank/meanwhile/commit/f0659a04c60d254fee8ff4f25694733933414f61))
* make the first setup easier for non-technical admins ([149033b](https://github.com/marank/meanwhile/commit/149033b6e32dbd6e85b89c7ae6f41eedaa8535ba))
* offer German with "du" as a language ([cf11859](https://github.com/marank/meanwhile/commit/cf11859d5610f06850ff9ffa16ec4d4645804331))
* start backend and frontend together with just dev ([d0aaffb](https://github.com/marank/meanwhile/commit/d0aaffb22462f5eae106944e45527114d566d381))


### Bug Fixes

* drop daphne and the Docker development stack, close open security alerts ([02a39ba](https://github.com/marank/meanwhile/commit/02a39ba5fc129585d470e0f1c3d17f83dfbba610))
* keep a developer's .env out of the mailer tests ([6dc84a9](https://github.com/marank/meanwhile/commit/6dc84a92802e1b27a9d97b36e6e977b4a7312ec9))
* keep the account's language when signing in on a shared browser ([bd9e540](https://github.com/marank/meanwhile/commit/bd9e5409ea9028cd3877bc1cf2f4654f42169f6a))
* line up the logo and favicon pickers and tell their best size ([17ea181](https://github.com/marank/meanwhile/commit/17ea181be30c7167c52930d6c73300f6e9baa4a1))
* list a calendar's members in the order they were granted ([03c2cd1](https://github.com/marank/meanwhile/commit/03c2cd1d64be39d1ef12e9737195eaeb74c8b48f))
* log in the server's time zone, with the offset to UTC ([cca0903](https://github.com/marank/meanwhile/commit/cca0903ffbf54cd76ccd8857e3dfb6f6dfc617dd))
* mark the API's error messages for translation ([870cce2](https://github.com/marank/meanwhile/commit/870cce264430b7116a2d8c5c31463e8cdc65ae34))
* name the sign-in, prompt, upload, comment and sharing fields for screen readers ([66a7cf0](https://github.com/marank/meanwhile/commit/66a7cf0d0668e8908276d1bd090bb6b3a48242ae))
* say how long the links in invitation and reset emails work ([6558411](https://github.com/marank/meanwhile/commit/65584111ed2ced4cdb498269560922f8f9baac3c))
* send no emails in allauth's own look ([70599f5](https://github.com/marank/meanwhile/commit/70599f5042f793ed7ff07f8e30d1f906354e38e3))
* show the app's own logo and icon while none is uploaded ([ad2ec9b](https://github.com/marank/meanwhile/commit/ad2ec9b06061201fb426575c9178e6f5e4146926))
* smaller rough edges of the setup ([e007216](https://github.com/marank/meanwhile/commit/e00721693205fd50db6e62cafa7c580cf4190884))
* smooth the first setup for non-technical admins ([887093d](https://github.com/marank/meanwhile/commit/887093d62e72f9d0266650b51288cfd9425051c9))
* tidy the container's log output ([370c4a0](https://github.com/marank/meanwhile/commit/370c4a0c84944418e28f91e895f2afa722775586))


### Dependencies

* Bump astral-sh/uv from `d3b601f` to `a3ea135` ([#8](https://github.com/marank/meanwhile/issues/8)) ([23a6fb9](https://github.com/marank/meanwhile/commit/23a6fb949e9757de6faa04c00cb176ac9bc5597f))
* Bump axllent/mailpit from v1.33 to v1.34 ([#7](https://github.com/marank/meanwhile/issues/7)) ([6476acd](https://github.com/marank/meanwhile/commit/6476acd0f342e0a826b0f2c63b84eb071ead285c))
* bump node from 24-alpine to 26-alpine ([#2](https://github.com/marank/meanwhile/issues/2)) ([c40fd02](https://github.com/marank/meanwhile/commit/c40fd021a39bfc042f600f4926504cdff72e004b))
* bump python from 3.14-slim-trixie to 3.15-slim-trixie ([#1](https://github.com/marank/meanwhile/issues/1)) ([17c2764](https://github.com/marank/meanwhile/commit/17c27646d6a319be3d43876bb8d63de61ee21044))
* Bump the backend group across 1 directory with 2 updates ([#9](https://github.com/marank/meanwhile/issues/9)) ([ea5908f](https://github.com/marank/meanwhile/commit/ea5908fbe87623515c24e93da63129c24525c694))
* Bump the frontend group across 1 directory with 6 updates ([#11](https://github.com/marank/meanwhile/issues/11)) ([560327e](https://github.com/marank/meanwhile/commit/560327ebf2b336b37e64a2e1b25c9d1fa9426a8a))


### Documentation

* keep the README for users, move development and operations details out ([cff0c32](https://github.com/marank/meanwhile/commit/cff0c32268c44780a7f40140f00aa0fa13465edc))
* rework the comments in compose.yml and .env.example ([6891dca](https://github.com/marank/meanwhile/commit/6891dca2d423e5a57c93c5848bb6dd0ed12820b1))
* show the month, week and list views in the README ([eadd9ff](https://github.com/marank/meanwhile/commit/eadd9ff47a574e899f4fc522d5cf5df55413e5db))
