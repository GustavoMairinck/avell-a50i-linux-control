# Protocolo DCHU (Clevo/Insyde): engenharia reversa do Control Center 3.0

Alvo: `09_Control_Center.zip` → Control Center Package **v6.093** (InstallShield),
Avell A50i (BIOS `1.07.01TBN`, base Clevo, Raptor Lake + RTX 3050).

## Ferramentas

| Etapa | Ferramenta |
|---|---|
| Inventário PE/.NET, metadados, membros, IOCTLs, GUIDs | **REA** (`inspect-managed-members`, `inspect-artifact`) |
| Extração dos cabs InstallShield v5+ | `unshield` (compilado da fonte) |
| Descompilação IL → C# | `ilspycmd` 11.1 |
| Exports e disassembly da DLL nativa | parser PE em Python + `objdump -M intel` |

## Pilha no Windows

```
Apps UWP/.NET (ControlCenter30, FanSpeedSetting, LedKeyboardSetting,
               BatteryPackUtility, EnergySave, FnKey)
        │ P/Invoke
InsydeDCHU.dll  ── GetDCHU_Data_Integer / GetDCHU_Data_Buffer /
        │          SetDCHU_Data / SetDCHU_DataEx / Read/WriteAppSettings
        │ DeviceIoControl(0x322400 IOCTL_ACPIBIOS_READ_METHOD)
AcpiBridge.sys  (ACPI\CLV0001, interface {86994c74-ad43-4812-b7e7-0c420b5c5fd7})
        │ IOCTL_ACPI_EVAL_METHOD
\_SB.DCHU._DSM
```

O `DCHUService.exe` também usa `0x322404` (WAIT_EVENT) e `0x322408`
(GET_NOTIFY_VALUE) para receber eventos das teclas Fn (`Arg001^<valor>`).

## A chamada

Disassembly de `GetDCHU_Data_Buffer` (0x180419a80) e `SetDCHU_Data`
(0x18041a550) na `InsydeDCHU.dll`: ambas montam a mesma estrutura
`ACPI_EVAL_INPUT_BUFFER_COMPLEX`:

```
MethodName = 0x4d53445f            ; "_DSM"
Arg0  Buffer(16) = 93f224e4-fbdc-4bbf-add6-db71bdc0afad   ; rdata 0x180bb0dc0
Arg1  Integer    = 0                ; revisão
Arg2  Integer    = <command>        ; argumento "command" da DLL
Arg3  Buffer(256)= <payload>        ; zeros para os "Get"
```

No Linux é só `acpi_evaluate_dsm(handle, &guid, 0, command, &buffer256)`.

`SetWMI(cmd, data)` envia 4 bytes LE. `SetWMI(cmd, sub, data)` coloca
`sub` no byte mais alto: `(sub << 24) | data`.

## Comandos usados

| cmd | Direção | Significado | Origem |
|---|---|---|---|
| 0x01 | get | evento de tecla Fn na fila | FnKey |
| 0x04 | pacote in/out | sub-protocolo EC (byte 0 = sub) | vários |
| 0x0c (12) | get buf | status das ventoinhas | FAN.Read_FanSpeed |
| 0x0d (13) | get buf | info do sistema: [12]=nº ventoinhas, [14]=modo inicial, [15]=tipo de teclado, [43] flags | FAN/BaseKB |
| 0x0e (14) | set buf | tabela de ventoinha personalizada | FAN.Write_WMI14 |
| 0x10 (16) | get int | bits de recurso (bit0 PowerMode, bit3 PerKey, bit4 RGB, bit7 FanSetting…) | InsydeDriver |
| 0x27 (39) | set | brilho do teclado branco (0..4 ou 0..5) | WhiteKB |
| 0x3d (61) | get int | brilho atual do teclado branco | WhiteKB |
| 0x60 (96) | get int | bits de recurso (bit7 anti-poeira, bit11 lightbar) | |
| 0x67 (103) | set | teclado RGB (ver abaixo) | RGBKB |
| 0x79 (121) | set | opções: `(sub<<24)\|valor` | vários |
| 0x7a (122) | get int | bits (bit12 lightbar, bit14 teclado branco 6 níveis, bit15 sem ventoinha, bit18 logo) | BaseKB |

### cmd 0x0c — ventoinhas
`rpm = buf[n]<<8 | buf[n+1]`; CPU n=2, GPU n=4, GPU2 n=6, sistema n=36.
Duty (0–255): 16/19/22/38. Temperatura (°C): 18/21/24/40.

### cmd 0x79 — sub-comandos
| sub | valor |
|---|---|
| 0x01 | modo das ventoinhas: 0 auto, 1 máximo, 5 Max-Q, 6 personalizado, 8 silencioso |
| 0x0e | offset de ventoinha (0–255) |
| 0x19 | **modo de energia**: 0 Silencioso, 1 Economia, 2 Desempenho (+0x40 turbo fan, +0x80 DTT), 3 Entretenimento |
| 0x1a | modo avião |
| 0x1c / 0x1d | AC-off / atualização de bateria (calibração) |
| 0x22 | restaura padrões de WMI13 |
| 0x28 | agendamento anti-poeira |
| 0x29 | executar anti-poeira agora |

### cmd 0x67 — teclado RGB (palavra de 32 bits)
| byte alto | significado |
|---|---|
| 0xF0/F1/F2 | cor da zona esquerda/centro/direita: `B<<16 \| R<<8 \| G` |
| 0xF3 / 0xF6 | lightbar / logo |
| 0xF4 | brilho (níveis 47/95/143/191) |
| 0xE0 | liga/desliga: bit12 ligado, bits 16-18 zonas |
| 0x10 / 0x33 / 0x70 / 0x80 / 0x90 / 0xA0 / 0xB0 | efeitos: respirar, ciclo, aleatório, dança, tempo, piscar, onda |

**Tipos de teclado (WMI13 byte 15):** 1 = branco, 2 = RGB 3 zonas (efeitos
no EC), **6/22 = RGB zona única** (caso do A50i). Para os tipos 6/22 o CC30
remove o painel de efeitos (`Page_LED_Device.xaml.cs`, `case 6:`), porque o EC
aceita as palavras de efeito mas o teclado não anima. No Linux, o driver
gera Respirar / Arco-íris / Aleatório / Piscar por software (timer de 80 ms
escrevendo a cor nas zonas `0xF0..0xF2`).

### Argumento do `_DSM` (importante)
O `AcpiBridge.sys` monta `ACPI_EVAL_INPUT_BUFFER_COMPLEX` com 4 argumentos:
GUID (buffer), revisão (inteiro), comando (inteiro) e **Arg3 do tipo
`ACPI_METHOD_ARGUMENT_PACKAGE_EX`** contendo o buffer de 256 bytes. O DSDT
lê com `ARGP = DerefOf (Arg2 [Zero])` dentro de `SCMD`, então o Linux precisa
passar `Package () { Buffer (256) }`. Com o buffer solto só o 1º byte chega
(leituras funcionam, escritas não).

### cmd 0x04 — pacotes EC (byte 0)
| sub | uso |
|---|---|
| 0x01, [1]=0..3, [6]=0xde | versão do EC (5 bytes por leitura, a partir de out[1]) |
| 0x01, [1]=0x09, [6]=0xc0 | status térmico |
| 0x16 | troca de GPU |
| 0x1e | **FlexiCharger leitura** → out[0]=ativo, out[1]=início, out[2]=fim |
| 0x1f | **FlexiCharger escrita** `[0x1f, ativo, início, fim]` |

### Eventos Fn (`Arg001`, byte baixo)
0x59 ciclo de modo de energia · 0x81/0x82 teclado −/+ · 0x8a ciclo de brilho ·
0x9e/0x9f liga/desliga teclado · 0x85 modo avião · 0x95 abrir Control Center ·
0xfc/0xfd touchpad.

## O que não foi portado
- **ReadAppSettings / WriteAppSettings**: só armazenamento das preferências
  do app no Windows; no Linux o estado fica em `/var/lib/avell-cc/state.json`.
- **Overclock de CPU/GPU** (`IntelOverclockingSDK`, `NVGPU_DLL`): SDKs
  proprietários de Windows. No Linux use `intel-undervolt` / `nvidia-smi`.
- **Teclado per-key** (`perkey_api.dll`, HID USB): só brilho e cor global via
  cmd 0x67.
- **Tabela de ventoinha personalizada** (cmd 0x0e): formato mapeado acima, sem
  interface ainda.
