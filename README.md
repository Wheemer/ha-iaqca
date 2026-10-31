*Please :star: this repo if you find it useful*

# Indoor Air Quality Canada Index for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacs-shield]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![Support me on Patreon][patreon-shield]][patreon]

[![Community Forum][forum-shield]][forum]

This component allows you to evaluate the air quality in any room, using data from various sensors installed there. Such as temperature, humidity, carbon dioxide sensors, etc.

The index is a simple Canadian-guidance-based home IAQ score using configured live sensors. It is not an official Government of Canada index.

I also suggest you [visit the support topic][forum] on the community forum.

![][exampleimg]

## Installation

### Install from HACS (recommended)

1. Have [HACS][hacs] installed, this will allow you to easily manage and track updates.
1. Search for "Indoor Air Quality Canada Index".
1. Click Install below the found integration.

... then if you want to use `configuration.yaml` to configure sensor...
1. Add `iaqca` sensor to your `configuration.yaml` file. See configuration examples below.
1. Restart Home Assistant

### Manual installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `iaqca`.
1. Download file `iaqca.zip` from the [latest release section][releases-latest] in this repository.
1. Extract _all_ files from this archive you downloaded in the directory (folder) you created.

... then if you want to use `configuration.yaml` to configure sensor...
1. Add `iaqca` sensor to your `configuration.yaml` file. See configuration examples below.
1. Restart Home Assistant

### Configuration Examples

To use this component in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
iaqca:
  kitchen:
    sources:
      temperature: sensor.kitchen_temperature
      humidity: sensor.kitchen_humidity
      co2: sensor.kitchen_eco2
      tvoc: sensor.kitchen_tvoc
    sensors:
      - iaq_level

  livingroom:
    name: "Living Room"
    sources:
      hcho: sensor.livingroom_formaldehyde
      pm:
        - sensor.livingroom_pm25
        - sensor.livingroom_pm10
```

<p align="center">* * *</p>
I put a lot of work into making this repo and component available and updated to inspire and help others! I will be glad to receive thanks from you — it will give me new strength and add enthusiasm:
<p align="center"><a href="https://www.patreon.com/join/limych?" target="_blank"><img src="http://khrolenok.ru/support_patreon.png" alt="Patreon" width="250" height="48"></a></p>

| Bitcoin                                                                                                                                                                                                                  | Ethereum                                                                                                                         | Monero                                                                                                                                                                              |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <a href="https://sochain.com/address/BTC/16yfCfz9dZ8y8yuSwBFVfiAa3CNYdMh7Ts" target="_blank"><img alt="Bitcoin" src="http://khrolenok.ru/support_btc.png" width="200"/></a><pre>16yfCfz9dZ8y8yuSwBFVfiAa3CNYdMh7Ts</pre> | <img alt="Ethereum" src="http://khrolenok.ru/support_eth.png" width="200"/><pre>0x9FB9429f9A85Fa2395Bb59e50452F64977435d61</pre> | <img alt="Monero" src="http://khrolenok.ru/support_xmr.png" width="200"/><pre>48Kt2ksKYxHg46T5sJ7feBXtndHhxk1JgYJwtwGG8Jb7asNFShRwUDtFgX2UvVThXa5GGyGbMCfNJX7YwFZBRDX43q4mT83</pre> |

### Configuration variables

Each room in the settings is defined by its own named group of parameters. You can specify the friendly name of this group (room), the sensors involved in the calculations, and which sensors you need to create for the output.

You can create as many groups as you need. But each group must have an unique name.

**name**:\
  _(string) (Optional) (Default value: deslugified group name)_\
  Friendly name to use in the frontend.

**sources**:\
  _(dictionary) (Required)_\
  Dictionary of sensors involved in the calculations. At least one sensor must be specified.

> **temperature**:\
> _(string) (Optional)_\
> Room temperature sensor entity ID.\
> Required sensor's unit of measurement: °C or °F
>
> **humidity**:\
> _(string) (Optional)_\
> Room humidity sensor entity ID.\
> Required sensor's unit of measurement: %
>
> **co2**:\
> _(string) (Optional)_\
> Room Carbon Dioxide (CO<sub>2</sub>) sensor entity ID.\
> Required sensor's unit of measurement: ppm, ppb, mg/m<sup>3</sup> or µg/m<sup>3</sup>
>
> **co**:\
> _(string) (Optional)_\
> Room Carbon Monoxide (CO) sensor entity ID.\
> Required sensor's unit of measurement: ppm, ppb, mg/m<sup>3</sup> or µg/m<sup>3</sup>
>
> **no2**:\
> _(string) (Optional)_\
> Room Nitrogen Dioxide (NO<sub>2</sub>) sensor entity ID.\
> Required sensor's unit of measurement: ppm, ppb, mg/m<sup>3</sup> or µg/m<sup>3</sup>
>
> **tvoc**:\
> _(string) (Optional)_\
> Room tVOC sensor entity ID.\
> Required sensor's unit of measurement: ppm, ppb, mg/m<sup>3</sup> or µg/m<sup>3</sup>\
> *Note:* Only one VOC source are allowed at once: **tvoc** or **voc_index**.
>
> **voc_index**:\
> _(string) (Optional)_\
> Room VOC sensor entity ID.\
> Required sensor's unit of measurement: None\
> Especially for SGP40 and SGP41 gas sensors that return a VOC value as an index from 0 to 500.\
> *Note:* Only one VOC source are allowed at once: **tvoc** or **voc_index**.
>
> **hcho**:\
> _(string) (Optional)_\
> Room Formaldehyde (HCHO; CH<sub>2</sub>O) sensor entity ID.\
> Required sensor's unit of measurement: ppm, ppb, mg/m<sup>3</sup> or µg/m<sup>3</sup>
>
> **radon**:\
> _(string) (Optional)_\
> Room Radon (Rn) sensor entity ID.\
> Required sensor's unit of measurement: Bq/m<sup>3</sup>
>
> **pm**:\
> _(string | list) (Optional)_\
> Room particulate matter sensors entity IDs.\
> Required sensor's unit of measurement: mg/m<sup>3</sup> or µg/m<sup>3</sup>

**sensors**:\
  _(list) (Optional) (Default value: all sensors below)_\
  List of sensors  you need to create for the output. The following sensors can be added:

> **iaq_index**:\
> The sensor displays the air quality in numerical form from 1 to 65. The higher the value, the better the air quality.
>
> **iaq_level**:\
> The sensor shows the air quality in a human-readable form. Possible values: Excellent, Good, Fair, Poor, Inadequate.

**_Note_**:\
The icon of `iaq_level` sensor changes its image depending on the value of the sensor.

## Track updates

You can automatically track new versions of this component and update it by [HACS][hacs].

## Troubleshooting

To enable debug logs use this configuration:
```yaml
# Example configuration.yaml entry
logger:
  default: info
  logs:
    custom_components.iaqca: debug
```
... then restart HA.

## Contributions are welcome!

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We have set up a separate document containing our
[contribution guidelines](CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## Authors & contributors

The original setup of this component is by [Andrey "Limych" Khrolenok](https://github.com/Limych).

For a full list of all authors and contributors,
check [the contributor's page][contributors].

This Home Assistant custom component was created and is updated using the [HA-Blueprint template](https://github.com/Limych/ha-blueprint). You can use this template to maintain your own Home Assistant custom components.

## License

MIT License

Copyright (c) 2019–2021 Andrey "Limych" Khrolenok

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

***

[component]: https://github.com/Wheemer/ha-iaqca
[commits-shield]: https://img.shields.io/github/commit-activity/y/Wheemer/ha-iaqca.svg?style=popout
[commits]: https://github.com/Wheemer/ha-iaqca/commits/master
[hacs-shield]: https://img.shields.io/badge/HACS-Default-orange.svg?style=popout
[hacs]: https://hacs.xyz
[exampleimg]: https://github.com/Wheemer/ha-iaqca/raw/dev/iaqca.jpg
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=popout
[forum]: https://community.home-assistant.io/t/indoor-air-quality-sensor-component/160474
[license]: https://github.com/Wheemer/ha-iaqca/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/Wheemer/ha-iaqca.svg?style=popout
[maintenance-shield]: https://img.shields.io/badge/maintainer-Andrey%20Khrolenok%20%40Limych-blue.svg?style=popout
[releases-shield]: https://img.shields.io/github/release/Wheemer/ha-iaqca.svg?style=popout
[releases]: https://github.com/Wheemer/ha-iaqca/releases
[releases-latest]: https://github.com/Wheemer/ha-iaqca/releases/latest
[user_profile]: https://github.com/Limych
[report_bug]: https://github.com/Wheemer/ha-iaqca/issues/new?template=bug_report.md
[suggest_idea]: https://github.com/Wheemer/ha-iaqca/issues/new?template=feature_request.md
[contributors]: https://github.com/Wheemer/ha-iaqca/graphs/contributors
[patreon-shield]: https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.vercel.app%2Fapi%3Fusername%3DLimych%26type%3Dpatrons&style=popout
[patreon]: https://www.patreon.com/join/limych
