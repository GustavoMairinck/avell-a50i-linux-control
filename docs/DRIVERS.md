# 00_Drivers_Automatizados.zip → equivalentes no Linux

Situação verificada no A50i (`lspci -k`, kernel 6.12.111). Só o DCHU precisava
de port; o restante já tem driver nativo no kernel ou um serviço equivalente.

| Pacote Windows | Hardware | Linux | Situação |
|---|---|---|---|
| AcpiBridge / AcpiBridge1 / DCHUService / InsydeDCHU | Clevo DCHU (CLV0001/2) | **avell_dchu** (este projeto) | portado |
| cui_dch / iigd_dch / igcc_dch | Intel UHD (Raptor Lake) | `i915` + mesa | ✅ ativo |
| nvlddmkm / nvhda / nvpcf / NVWMI | RTX 3050 | `nvidia` 555 (DKMS) | ✅ ativo |
| Netwtw* | Wi-Fi Intel CNVi | `iwlwifi` | ✅ ativo |
| ibtusb / IntcBtLE / IntcBTAu | Bluetooth Intel | `btusb`/`btintel` | ✅ |
| rt640x64 | Realtek RTL8111 | `r8169` | ✅ ativo |
| RTKVHD64 / Realtek APO / HSA / Creative | Áudio HDA | `snd_hda_intel` + PipeWire | ✅ ativo (efeitos Sound Blaster não existem no Linux) |
| IntcSST / IntcDMic / IntcSDW / IntcAudioBus | DSP de áudio Intel | `snd_sof` (só se o BIOS usar DSP) | ✅ hoje em HDA |
| heci / DAL / iclsClient / MEWMIProv | Intel ME | `mei_me` | ✅ ativo |
| iaLPSS2_I2C / GPIO | I²C / GPIO (touchpad) | `intel-lpss` | ✅ ativo |
| bhtsddr | Leitor SD O2 Micro | `sdhci-pci` | ✅ ativo |
| alderlake/raptorlake system, DmaSec | Chipset | kernel | ✅ |
| dtt_sw / dtt_ext / Dptf* / ipf_* | Intel Dynamic Tuning (térmico) | `int3400_thermal`, `proc_thermal` + **thermald** | ⚠️ `thermald` não instalado, recomendado |
| gna | Intel GNA (acelerador de voz) | `intel_gna` (fora do kernel principal) | ➖ desnecessário |
| HidEventFilter | Botões ACPI/HID | `intel-hid` | ✅ |
| LT6911Au / snDMFT / xvdd / gameflt / prnms* | captura HDMI, câmera virtual, filtros de jogo, impressoras virtuais | — | ➖ só Windows |

Instalar o thermald:

```bash
sudo apt install thermald
```
