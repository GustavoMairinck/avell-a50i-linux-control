# avell-a50i-linux-control

**Control Center nativo para Linux no Avell A50i** (e provavelmente outros
Avell/Clevo com a interface ACPI `CLV0001` / `\_SB.DCHU`).

Port do **Control Center 3.0** (Clevo/Insyde) do Windows, feito por engenharia
reversa com [REA](https://github.com/morluto/rea), `ilspycmd` e análise do
DSDT. Inclui um driver de kernel (DKMS), um app GTK4/libadwaita e a CLI
`avellctl`.

> 🇺🇸 *Native Linux replacement for the Avell/Clevo Control Center: kernel
> driver (power profiles, fan monitoring/modes, RGB keyboard with effects,
> battery charge limit, Fn hotkeys) + GTK4 app. Tested on Avell A50i.*

> ⚠️ Projeto **não oficial**, sem vínculo com a Avell ou a Clevo. Use por sua
> conta e risco.

## Recursos

| Recurso | Windows | Linux |
|---|---|---|
| Modos de energia (Silencioso, Economia, Entretenimento, Desempenho) | CC30 | `platform_profile` → **menu de energia do GNOME** + app |
| Ventoinhas: RPM, temperatura, duty | FanSpeedSetting | `hwmon` (`sensors`, app) |
| Modo das ventoinhas (auto, silencioso, máximo, Max-Q) | FanSpeedSetting | app / `avellctl fan` |
| Limpeza anti-poeira | FanSpeedSetting | app / `avellctl antidust` |
| Luz do teclado (branco ou RGB, cor, brilho) | LedKeyboardSetting | LED `avell::kbd_backlight` + app |
| Efeitos do teclado | só RGB 3 zonas | também no **RGB de zona única** (gerados pelo driver) |
| Limite de carga (FlexiCharger) | BatteryUtility | `charge_control_*_threshold` (**"Preservar saúde da bateria" do GNOME**) + app |
| Teclas Fn (luz do teclado, modo de energia, avião, touchpad) | DCHUService + FnKey | tratadas no driver / dispositivo de entrada |

## Compatibilidade

Testado em:

| Modelo | BIOS / EC | Teclado | Sistema |
|---|---|---|---|
| Avell A50i (HYB A50i) | 1.07.01TBN / 1.07.03 | RGB zona única (tipo 6) | Debian 13, kernel 6.12, GNOME 48 |

Outros Avell/Clevo com `CLV0001` devem funcionar. Confira com
`ls /sys/bus/acpi/devices | grep CLV0001`. Abra uma issue com a saída de
`avellctl` e `sudo dmesg | grep avell` para adicionar seu modelo.

## Instalar

Requisitos: Debian/Ubuntu (usa `apt` para instalar `dkms`, headers do kernel
e GTK4/libadwaita). Com Secure Boot ativo, a chave MOK do DKMS precisa estar
registrada.

```bash
git clone https://github.com/LuizRojas/avell-a50i-linux-control.git
cd avell-a50i-linux-control
./install.sh
```

Isso compila o módulo via DKMS (recompila sozinho a cada atualização do
kernel), instala `avellctl`, o app **Avell Control Center**, a regra polkit
(o usuário local ativo altera o hardware sem senha) e o serviço que restaura
suas configurações no boot.

Remover: `./uninstall.sh`

## Usar

Abra **Avell Control Center** no menu de aplicativos, ou use o terminal:

```bash
avellctl                       # estado + sensores
avellctl profile performance   # quiet | low-power | balanced | performance
avellctl fan silent            # auto | silent | max | maxq
avellctl kbd 3                 # brilho do teclado
avellctl color 00aaff          # cor (RGB)
avellctl effect cycle          # static breathe cycle flash random (+ wave dance tempo no 3 zonas)
avellctl charge 70 90          # carregar abaixo de 70%, parar em 90%
sudo avellctl raw 0x0d         # chamada _DSM bruta (diagnóstico)
```

## Estrutura

```
driver/      módulo de kernel avell_dchu (DKMS)
avell_cc/    biblioteca, CLI, helper privilegiado e app GTK4/libadwaita
data/        polkit, systemd, .desktop
docs/        PROTOCOLO.md (engenharia reversa) e DRIVERS.md (drivers do Windows → Linux)
```

## Como funciona

Toda a pilha do Windows (`AcpiBridge.sys` + `InsydeDCHU.dll` + apps .NET) se
resume a uma chamada ACPI:

```
\_SB.DCHU._DSM(93f224e4-fbdc-4bbf-add6-db71bdc0afad, 0, <comando>, Package { Buffer(256) })
```

O driver faz essa mesma chamada com `acpi_evaluate_dsm()` e expõe tudo pelas
interfaces padrão do kernel. A tabela completa de comandos e os detalhes estão
em [docs/PROTOCOLO.md](docs/PROTOCOLO.md).

## Segurança

O driver só emite as chamadas `_DSM` que o Control Center oficial emite. O
dispositivo `/dev/avell-dchu` (chamadas brutas) exige root (`CAP_SYS_ADMIN`).
O helper do polkit aceita apenas uma lista fechada de operações e valores.

Este repositório não contém nenhum binário, instalador ou código do software
original; só código próprio e a documentação do protocolo, para
interoperabilidade.

## Licença

GPL-2.0-or-later. Veja [LICENSE](LICENSE).
