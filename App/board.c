/* Copyright 2025 muzkr https://github.com/muzkr
 * Copyright 2023 Dual Tachyon
 * https://github.com/DualTachyon
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *     Unless required by applicable law or agreed to in writing, software
 *     distributed under the License is distributed on an "AS IS" BASIS,
 *     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *     See the License for the specific language governing permissions and
 *     limitations under the License.
 */

#include <string.h>

#ifdef ENABLE_FMRADIO
    #include "app/fm.h"
#endif
#include "board.h"
#include "py32f071_ll_bus.h"
#include "py32f071_ll_gpio.h"
#include "py32f071_ll_rcc.h"
#include "py32f071_ll_adc.h"
#include "driver/voice.h"
#include "driver/backlight.h"
#ifdef ENABLE_FMRADIO
    #include "driver/bk1080.h"
#endif

#include "driver/crc.h"
#include "driver/py25q16.h"
#include "driver/flash.h"
#include "driver/gpio.h"
#include "driver/systick.h"
#include "driver/system.h"
#include "driver/st7565.h"
#include "frequencies.h"
#include "helper/battery.h"
#include "misc.h"
#include "settings.h"
#if defined(ENABLE_OVERLAY)
    #include "sram-overlay.h"
#endif

#if defined(ENABLE_OVERLAY)
    void BOARD_FLASH_Init(void)
    {
        FLASH_Init(FLASH_READ_MODE_1_CYCLE);
        FLASH_ConfigureTrimValues();
        SYSTEM_ConfigureClocks();

        overlay_FLASH_MainClock       = 48000000;
        overlay_FLASH_ClockMultiplier = 48;

        FLASH_Init(FLASH_READ_MODE_2_CYCLE);
    }
#endif

void BOARD_GPIO_Init(void)
{
    LL_IOP_GRP1_EnableClock(
        LL_IOP_GRP1_PERIPH_GPIOA   //
        | LL_IOP_GRP1_PERIPH_GPIOB //
        | LL_IOP_GRP1_PERIPH_GPIOC //
        | LL_IOP_GRP1_PERIPH_GPIOF //
    );

    LL_GPIO_InitTypeDef InitStruct;
    LL_GPIO_StructInit(&InitStruct);
    InitStruct.OutputType = LL_GPIO_OUTPUT_PUSHPULL;
    InitStruct.Pull = LL_GPIO_PULL_UP;
    InitStruct.Speed = LL_GPIO_SPEED_FREQ_VERY_HIGH;

    // ---------------------
    // Input pins

    InitStruct.Mode = LL_GPIO_MODE_INPUT;

    // Keypad rows: PB15:12
    InitStruct.Pin = LL_GPIO_PIN_15 | LL_GPIO_PIN_14 | LL_GPIO_PIN_13 | LL_GPIO_PIN_12;
    LL_GPIO_Init(GPIOB, &InitStruct);

    // PTT: PB10
    InitStruct.Pin = LL_GPIO_PIN_10;
    LL_GPIO_Init(GPIOB, &InitStruct);

    // -----------------------
    //  Output pins

    LL_GPIO_SetOutputPin(GPIOA, LL_GPIO_PIN_6); // LCD A0
    LL_GPIO_SetOutputPin(GPIOB, LL_GPIO_PIN_2); // LCD CS

    InitStruct.Mode = LL_GPIO_MODE_OUTPUT;

    // Keypad cols: PB6:3
    InitStruct.Pin = LL_GPIO_PIN_6 | LL_GPIO_PIN_5 | LL_GPIO_PIN_4 | LL_GPIO_PIN_3;
    LL_GPIO_Init(GPIOB, &InitStruct);

    // Audio PA: PA8
    // LCD A0: PA6
    // SPI flash CS: PA3
    InitStruct.Pin = LL_GPIO_PIN_8 | LL_GPIO_PIN_6 | LL_GPIO_PIN_3;
    LL_GPIO_Init(GPIOA, &InitStruct);

    // BK4819 SCK: B8
    // BK4819 SDA: B9
    // LCD CS: PB2
    InitStruct.Pin = LL_GPIO_PIN_9 | LL_GPIO_PIN_8 | LL_GPIO_PIN_2;
    LL_GPIO_Init(GPIOB, &InitStruct);

    // TODO: conditional compile per ENABLE_FLASHLIGHT
    // Flashlight: PC13
    InitStruct.Pin = LL_GPIO_PIN_13;
    LL_GPIO_Init(GPIOC, &InitStruct);

#ifdef ENABLE_FMRADIO
    // BK1080 SCK: PF5
    // BK1080 SDA: PF6
    InitStruct.Pin = LL_GPIO_PIN_6 | LL_GPIO_PIN_5;
    LL_GPIO_Init(GPIOF, &InitStruct);
#endif

    // Backlight: PF8
    // BK4819 CS: PF9
    InitStruct.Pin = LL_GPIO_PIN_9 | LL_GPIO_PIN_8  ;
    LL_GPIO_Init(GPIOF, &InitStruct);

#ifndef ENABLE_SWD
    // A14:13
    InitStruct.Pin = LL_GPIO_PIN_14 | LL_GPIO_PIN_13;
    LL_GPIO_Init(GPIOA, &InitStruct);
#endif // ENABLE_SWD
}

void BOARD_ADC_Init(void)
{
    LL_IOP_GRP1_EnableClock(LL_IOP_GRP1_PERIPH_GPIOB);
    LL_GPIO_SetPinMode(GPIOB, LL_GPIO_PIN_0 | LL_GPIO_PIN_1, LL_GPIO_MODE_ANALOG);

    LL_APB1_GRP2_EnableClock(LL_APB1_GRP2_PERIPH_ADC1);
    LL_RCC_SetADCClockSource(LL_RCC_ADC_CLKSOURCE_PCLK_DIV4);

    LL_ADC_SetCommonPathInternalCh(ADC1_COMMON, LL_ADC_PATH_INTERNAL_TEMPSENSOR); // enables VREFINT, too
    LL_ADC_SetResolution(ADC1, LL_ADC_RESOLUTION_12B);
    LL_ADC_SetDataAlignment(ADC1, LL_ADC_DATA_ALIGN_RIGHT);
    LL_ADC_SetSequencersScanMode(ADC1, LL_ADC_SEQ_SCAN_DISABLE);
    LL_ADC_REG_SetTriggerSource(ADC1, LL_ADC_REG_TRIG_SOFTWARE);
    LL_ADC_REG_SetContinuousMode(ADC1, LL_ADC_REG_CONV_SINGLE);
    LL_ADC_REG_SetDMATransfer(ADC1, LL_ADC_REG_DMA_TRANSFER_NONE);
    LL_ADC_REG_SetSequencerLength(ADC1, LL_ADC_REG_SEQ_SCAN_DISABLE);
    LL_ADC_REG_SetSequencerDiscont(ADC1, LL_ADC_REG_SEQ_DISCONT_DISABLE);
    LL_ADC_REG_SetSequencerDiscont(ADC1, LL_ADC_REG_SEQ_DISCONT_DISABLE);
    LL_ADC_REG_SetSequencerRanks(ADC1, LL_ADC_REG_RANK_1, LL_ADC_CHANNEL_8);
    LL_ADC_SetChannelSamplingTime(ADC1, LL_ADC_CHANNEL_8, LL_ADC_SAMPLINGTIME_41CYCLES_5);
    LL_ADC_SetChannelSamplingTime(ADC1, LL_ADC_CHANNEL_TEMPSENSOR, LL_ADC_SAMPLINGTIME_239CYCLES_5); // 15us sample time (PY32F071_Datasheet_V0.8.pdf 5.3.15). ADC clock is PCLK/4=48 MHz/4=12 MHz, 239.5 cycles=20us is > 15us
    LL_ADC_SetChannelSamplingTime(ADC1, LL_ADC_CHANNEL_VREFINT, LL_ADC_SAMPLINGTIME_239CYCLES_5); // 15us sample time (PY32F071_Datasheet_V0.8.pdf 5.3.15). ADC clock is PCLK/4=48 MHz/4=12 MHz, 239.5 cycles=20us is > 15us

    LL_ADC_StartCalibration(ADC1);
    while (LL_ADC_IsCalibrationOnGoing(ADC1))
        ;

    LL_ADC_Enable(ADC1);

    SYSTICK_DelayUs(120); // wait max ADC startup time (PY32F071_Datasheet_V0.8.pdf 5.3.19)
}

void BOARD_ADC_GetBatteryInfo(uint16_t *pVoltage, uint16_t *pCurrent)
{
    LL_ADC_REG_StartConversionSWStart(ADC1);
    while (!LL_ADC_IsActiveFlag_EOS(ADC1))
        ;
    LL_ADC_ClearFlag_JEOS(ADC1);

    *pVoltage = LL_ADC_REG_ReadConversionData12(ADC1);
    *pCurrent = 0;
}



// temperature characteristics (PY32F071_Datasheet_V0.8.pdf 5.3.19)
#define TEMPSENSOR_AVGSLOPE_UV   2500  // Avg_Slope, typ. (uV/DegC)
#define TEMPSENSOR_V30_MV        760   // V30, typ. (mV at 30 degC)
#define TEMPSENSOR_CAL_TEMP      30    // degC
#define VREFINT_TYP_MV           1200  // VREFINT, typ. (mV)

// Selects Channel as the (single) regular sequencer rank and returns its
// raw 12-bit conversion result. Shared helper for both internal channels;
// BOARD_ADC_GetBatteryInfo() above leaves the sequencer parked on the
// battery channel (8) between calls, so this restores that afterwards.
static uint16_t ADC_ReadChannel(uint32_t Channel)
{
    LL_ADC_REG_SetSequencerRanks(ADC1, LL_ADC_REG_RANK_1, Channel);
    LL_ADC_REG_StartConversionSWStart(ADC1);
    while (!LL_ADC_IsActiveFlag_EOS(ADC1))
        ;
    LL_ADC_ClearFlag_JEOS(ADC1);

    return LL_ADC_REG_ReadConversionData12(ADC1);
}



int32_t BOARD_ADC_GetTemperature(void)
{
    const uint16_t vrefintRaw = ADC_ReadChannel(LL_ADC_CHANNEL_VREFINT);
    const uint16_t tempRaw    = ADC_ReadChannel(LL_ADC_CHANNEL_TEMPSENSOR);

    // Restore the sequencer to the battery-voltage channel used by
    // BOARD_ADC_GetBatteryInfo().
    LL_ADC_REG_SetSequencerRanks(ADC1, LL_ADC_REG_RANK_1, LL_ADC_CHANNEL_8);

    const uint32_t vddaMv = (VREFINT_TYP_MV * __LL_ADC_DIGITAL_SCALE(LL_ADC_RESOLUTION_12B)) / vrefintRaw;

    return __LL_ADC_CALC_TEMPERATURE_TYP_PARAMS(
        TEMPSENSOR_AVGSLOPE_UV,
        TEMPSENSOR_V30_MV,
        TEMPSENSOR_CAL_TEMP,
        vddaMv,
        tempRaw,
        LL_ADC_RESOLUTION_12B);
}



void BOARD_Init(void)
{
    BOARD_GPIO_Init();
    BACKLIGHT_InitHardware();
    BOARD_ADC_Init();
#ifdef ENABLE_VOICE
    VOICE_Init();
#endif
    PY25Q16_Init();
    ST7565_Init();
#ifdef ENABLE_FMRADIO
    BK1080_Init0();
#endif

#if defined(ENABLE_UART) || defined(ENABLED_AIRCOPY)
    CRC_Init();
#endif

}
