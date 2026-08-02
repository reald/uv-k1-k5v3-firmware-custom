/* Copyright 2024 Dennis Real
 * https://github.com/reald
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

#ifdef ENABLE_ARDF

#include "app/ardf.h"
#include "driver/bk4819.h"
#include "driver/system.h"
#include "audio.h"
#include "misc.h"
#include "settings.h"
#include "ui/main.h"
#include "ui/ui.h"
#include "ui/ardf.h"



uint8_t ardf_gain_index[2][ARDF_NUM_FOX_MAX];
t_ardf_gain_cheat_type ardf_type_gain_cheat[2][ARDF_NUM_FOX_MAX];

// {0x03BE, -7},   //  0 .. 3 5 3 6 ..   0dB  -4dB  0dB  -3dB ..  -7dB original
#define ARDF_ORIG_GAIN_DB -7

t_ardf_gain_table ardf_gain_table[] =
{
   {0x0000, -60}, // 0: 0, -60dB
   {0x0080, -55}, // 1: 128, -55dB
   {0x0051, -50}, // 2: 81, -50dB
   {0x00B1, -45}, // 3: 177, -45dB
   {0x00F1, -40}, // 4: 241, -40dB
   {0x00DA, -35}, // 5: 218, -35dB
   {0x0065, -30}, // 6: 101, -30dB
   {0x0215, -25}, // 7: 533, -25dB
   {0x026E, -20}, // 8: 622, -20dB
   {0x028F, -15}, // 9: 655, -15dB
   {0x02BF, -10}, // 10: 703, -10dB
   {0x03DD, -5}, // 11: 989, -5dB
   {0x03FF, 0}, // 12: 1023, 0dB
};


uint32_t          gARDFTime10ms = 0;
uint32_t          gARDFFoxDuration10ms = ARDF_DEFAULT_FOX_DURATION;  /* 60s * 100 ticks per second */
uint32_t          gARDFFoxDuration10ms_corr = ARDF_DEFAULT_FOX_DURATION + (ARDF_DEFAULT_FOX_DURATION * ARDF_CLOCK_CORR_TICKS_PER_MIN)/6000;
uint8_t           gARDFNumFoxes = ARDF_DEFAULT_NUM_FOXES;
uint8_t           gARDFActiveFox = 0;
uint8_t           gARDFGainRemember = ARDF_DEFAULT_GAIN_REMEMBER; /* remember gain on VFO 1 by default. */
uint8_t           gARDFCycleEndBeep_s = ARDF_CYCLE_END_BEEP_S_DEFAULT;
bool              gARDFDFSimpleMode = false;
bool              gARDFPlayEndBeep = false;
unsigned int      gARDFRssiMax = 0; /* max rssi of last half second */
uint8_t           gARDFMemModeFreqToggleCnt_s = 0; /* toggle memory bank/frequency display every x s */
bool              gARDFRequestSaveEEPROM = false;
int16_t           gARDFClockCorrAddTicksPerMin = ARDF_CLOCK_CORR_TICKS_PER_MIN;
uint32_t          gARDFGainCheatBaseFrequency[2] = {0, 0};

#ifdef ARDF_ENABLE_SHOW_DEBUG_DATA
int16_t           gARDFdebug = 0;
int16_t           gARDFdebug2 = 0;
#endif

static uint8_t    last_vfo = 0;



static void ARDF_ChangeGainCheat(t_ardf_gain_cheat_type oldtype, t_ardf_gain_cheat_type newtype)
{
   uint8_t vfo = gEeprom.RX_VFO;
   uint8_t activefox = gARDFActiveFox;
   uint32_t frequency = 0;
   
   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }

   if ( (oldtype == ARDF_NO_GAIN_CHEAT) && (newtype == ARDF_INT_LNA_OFF) )
   {
      // gain cheat freshly activated. save base frequency
      gARDFGainCheatBaseFrequency[vfo] = gTxVfo->freq_config_RX.Frequency * 10;
   }

   if ( newtype == ARDF_INT_LNA_OFF )
   {
      frequency = gARDFGainCheatBaseFrequency[vfo]/10;
   }
   else if ( newtype == ARDF_HARMONIC_2 )
   {
      // second harmonic
      frequency = (gARDFGainCheatBaseFrequency[vfo] * 2) / 10;
   }
   else if ( newtype == ARDF_HARMONIC_3 )
   {
      // third harmonic
      frequency = (gARDFGainCheatBaseFrequency[vfo] * 3) / 10;
   }
   else if ( newtype == ARDF_NO_GAIN_CHEAT )
   {
      // lback to normal. aktivate LNA again
      frequency = gARDFGainCheatBaseFrequency[vfo]/10;
   }

   if ( RX_freq_check(frequency) < 0 )
   {
      // frequency not allowed
      gARDFPlayEndBeep = true;
      AUDIO_PlayBeep( BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL );
      gARDFPlayEndBeep = false;

      return;
   }

   gTxVfo->freq_config_RX.Frequency = frequency;
   BK4819_SetFrequency(frequency);
   // not gRequestSaveChannel = 1 because gain cheat must not be saved!

   uint16_t reg = BK4819_ReadRegister(BK4819_REG_30);
   BK4819_WriteRegister(BK4819_REG_30, reg & ~BK4819_REG_30_ENABLE_VCO_CALIB);
   BK4819_WriteRegister(BK4819_REG_30, reg);

   if ( newtype == ARDF_INT_LNA_OFF )
   {
      // disable internal lna
      BK4819_ToggleGpioOut(BK4819_GPIO4_PIN32_VHF_LNA, false);
      BK4819_ToggleGpioOut(BK4819_GPIO3_PIN31_UHF_LNA, false); 
   }
   else
   {
      // set LNA for new frequency
      BK4819_PickRXFilterPathBasedOnFrequency(frequency);
   }

   // update gain cheat type
   ardf_type_gain_cheat[vfo][activefox] = newtype;

   return;
}



void ARDF_10ms(void)
{
   static uint16_t rssimaxhold_cnt = 0;
   static uint8_t vfo_gaincheat_delay = 0;

   uint8_t vfo = gEeprom.RX_VFO;
   uint8_t activefox = gARDFActiveFox;

   rssimaxhold_cnt++;

   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }

   if ( vfo != last_vfo )
   {
      // vfo swapped
      vfo_gaincheat_delay++;
   }


   if ( vfo_gaincheat_delay >= 10 ) // must be at least 6
   {
      // workaround: do gain cheat has to be delayed after vfo change.
      // close to strong transmitters devices will not receive anything if gain cheat happens too fast after vfo change

      if ( (gSetting_ARDFEnable)
           && (ardf_type_gain_cheat[vfo][activefox] != ARDF_NO_GAIN_CHEAT) )
      {
         ARDF_DoGainCheat(); // vfo changed and new vfo has gain cheat on. activate it
      }
      last_vfo = vfo;
      vfo_gaincheat_delay = 0;
   }

   if ( gARDFTime10ms >= gARDFFoxDuration10ms_corr )
   {
      // new fox cycle
      gARDFTime10ms = 0;
      

      // clean up old fox: undo gain cheat if active.
      // only necessary if gain remember is active, because without gain remember the gain setting is kept for next fox
      if ( (gSetting_ARDFEnable)
           && (ARDF_ActVfoHasGainRemember(vfo) != false)
           && (ardf_type_gain_cheat[vfo][gARDFActiveFox] != ARDF_NO_GAIN_CHEAT)
           && (vfo_gaincheat_delay == 0) ) // vfo not changed shortly. (undo gain cheat would already been done in COMMON_SwitchVFOs() )
      {
         ARDF_UndoGainCheat(); // undo gain cheat. gain cheat will be restored if fox becomes active again
      }

      // switch to next fox
      if ( (gARDFActiveFox + 1) >= gARDFNumFoxes ) // gARDFNumFoxes can be 0 if timing is disabled
      {
         gARDFActiveFox = 0;
      }
      else
      {
         gARDFActiveFox++;
      }

      if ( gSetting_ARDFEnable )
      {
         // recall last gain index if needed
         ARDF_ActivateGainIndex();

         // restore gain cheat if gain remember is active. only necessary if gain remember is active, because without gain remember the gain setting is kept for next fox
         if ( (ARDF_ActVfoHasGainRemember(vfo) != false)
              && (ardf_type_gain_cheat[vfo][gARDFActiveFox] != ARDF_NO_GAIN_CHEAT)
              && (vfo_gaincheat_delay == 0) ) // vfo not changed shortly
         {
            ARDF_DoGainCheat();
         }
      }
      
      if ( gScreenToDisplay == DISPLAY_ARDF )
      {
         // update complete screen
         UI_DisplayARDF();
      }   

   }
   else if ( (gScreenToDisplay == DISPLAY_ARDF) && ( (gARDFTime10ms % 20) == 0) )
   {
      // update most important values ~5 times per second
      if ( gARDFNumFoxes > 0 )
      {
         UI_DisplayARDF_Timer();
      }

      if ( rssimaxhold_cnt >= 80 )
      {
         // reset max level after 0.8s
         gARDFRssiMax = BK4819_GetRSSI();
      }
      UI_DisplayARDF_RSSI(true);

#ifdef ARDF_ENABLE_SHOW_DEBUG_DATA
      UI_DisplayARDF_Debug();
#elif defined(ENABLE_AGC_SHOW_DATA)
      UI_MAIN_PrintAGC(true);
#else
      center_line = CENTER_LINE_RSSI;

      if ( gARDFDFSimpleMode != false )
      {
         UI_DisplayARDF_RSSIBar_Simple(true);
      }
      else if( !(gLowBattery && !gLowBatteryConfirmed) )
      {
         UI_DisplayRSSIBar(true);
      }

#endif

   }
   else if ( (gScreenToDisplay == DISPLAY_ARDF) && ( (gARDFTime10ms % 5) == 0) )
   {
      // reduce call rate if i2c traffic is too high
      unsigned int rssi = BK4819_GetRSSI();
      if ( rssi > gARDFRssiMax )
      {
         gARDFRssiMax = rssi;
         rssimaxhold_cnt = 0;
      }
   }

}



void ARDF_500ms(void)
{
   static uint8_t u8Secnd = 0;

   if ( gSetting_ARDFEnable && gScreenToDisplay==DISPLAY_MAIN )
   {
      // switch to ardf screen
      GUI_SelectNextDisplay(DISPLAY_ARDF);
   }
   else if ( !gSetting_ARDFEnable && gScreenToDisplay==DISPLAY_ARDF )
   {
      // ARDF is off now. switch back to main screen
      GUI_SelectNextDisplay(DISPLAY_MAIN);
   }


   u8Secnd++;
   
   if ( u8Secnd >= 2 )
   {

      // update status bar every second
      gUpdateStatus = 1;
      u8Secnd = 0;

      // counter for memory mode / frequency display toggle
      gARDFMemModeFreqToggleCnt_s++;

      if ( (gScreenToDisplay==DISPLAY_ARDF)
            && (gARDFMemModeFreqToggleCnt_s == ARDF_MEM_MODE_FREQ_TOGGLE_S) )
      {
         // screen update only really necessary in memory mode
         UI_DisplayARDF_FreqCh(true);
      }
      else if ( (gScreenToDisplay==DISPLAY_ARDF)
                 && (gARDFMemModeFreqToggleCnt_s >= (2 * ARDF_MEM_MODE_FREQ_TOGGLE_S)) )
      {
         gARDFMemModeFreqToggleCnt_s = 0;
         // screen update only really necessary in memory mode
         // UI_DisplayARDF_FreqCh(); // frequency update would be sufficient but problems deleting pixels
         UI_DisplayARDF();
      }


      // generate fox cycle end signal

      if ( (gScreenToDisplay==DISPLAY_ARDF)
           && (gARDFNumFoxes > 0)
           && (gARDFCycleEndBeep_s != 0)
           && (ARDF_GetRestTime_s() == gARDFCycleEndBeep_s) )
      {
         gARDFPlayEndBeep = true;
         AUDIO_PlayBeep( BEEP_880HZ_60MS_DOUBLE_BEEP );
         gARDFPlayEndBeep = false;
      }

   }

   if ( gARDFRequestSaveEEPROM != false )
   {
      // save ARDF settings to eeprom
      gARDFRequestSaveEEPROM = false;
      SETTINGS_SaveARDF();
   }

}



void ARDF_init(void)
{
   uint8_t gain_index = ARDF_GAIN_INDEX_DEFAULT;

   if ( gARDFDFSimpleMode != false )
   {
      gain_index = ARDF_GAIN_INDEX_DF_SIMPLE;
   }

   for ( uint8_t i=0; i<ARDF_NUM_FOX_MAX; i++ )
   {
      // default gain index
      ardf_gain_index[0][i] = gain_index;
      ardf_gain_index[1][i] = gain_index;

      // no gain cheat by default
      ardf_type_gain_cheat[0][i] = ARDF_NO_GAIN_CHEAT;
      ardf_type_gain_cheat[1][i] = ARDF_NO_GAIN_CHEAT;
   }

   last_vfo = gEeprom.RX_VFO;
}



void ARDF_GainIncr(void)
{
   uint8_t vfo = gEeprom.RX_VFO;
   uint8_t activefox = gARDFActiveFox;
   
   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }
   

   if ( (ardf_gain_index[vfo][activefox] == 0)
        && (ardf_type_gain_cheat[vfo][activefox] != ARDF_NO_GAIN_CHEAT)
      )
   {
      // reduce gain cheat
      ARDF_ChangeGainCheat( ardf_type_gain_cheat[vfo][activefox], ardf_type_gain_cheat[vfo][activefox]-1 );
   }
   else if ( ardf_gain_index[vfo][activefox] < (sizeof(ardf_gain_table)/sizeof(t_ardf_gain_table) - 1) )
   {
      // normal gain increase
      ardf_gain_index[vfo][activefox]++;
   }
   else
   {
      // upper boundary already reached. do nothing
   }

}



void ARDF_GainDecr(void)
{
   uint8_t vfo = gEeprom.RX_VFO;
   uint8_t activefox = gARDFActiveFox;

   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }


   if ( ardf_gain_index[vfo][activefox] > 0 )
   {
      // normal gain decrease
      ardf_gain_index[vfo][activefox]--;
   }
   else if ( (ardf_gain_index[vfo][activefox] == 0)
             && (gSetting_ARDFEnable != false)
             && (gARDFDFSimpleMode == false)
             && (ardf_type_gain_cheat[vfo][activefox] < ARDF_HARMONIC_3 )
           )
   {
      // increase gain cheat if ardf enabled (but not in DF simple)
      ARDF_ChangeGainCheat( ardf_type_gain_cheat[vfo][activefox], ardf_type_gain_cheat[vfo][activefox]+1 );
   }
   else
   {
      // gain cheat disabled or min gain finally reached. do nothing.
   }

}



uint8_t ARDF_Get_GainIndex(uint8_t vfo)
{
   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // remember fox gains not on this vfo
      return ardf_gain_index[vfo][0];
   }
   else
   {
      return ardf_gain_index[vfo][gARDFActiveFox];
   }

}



bool ARDF_ActVfoHasGainRemember(uint8_t vfo)
{
   /* "OFF", 0
      "VFO A", 1
      "VFO B", 2
      "BOTH" 3 */
   
   if ( (vfo+1) & gARDFGainRemember )
   {
      return true;
   }
   else
   {
      return false;
   }

}



void ARDF_ActivateGainIndex(void)
{
   BK4819_WriteRegister( BK4819_REG_13, ardf_gain_table[ ARDF_Get_GainIndex(gEeprom.RX_VFO) ].reg_val );
   gARDFRssiMax = 0;
   gUpdateDisplay = true;
}



int32_t ARDF_GetRestTime_s(void)
{
   return (int32_t)(gARDFFoxDuration10ms - gARDFTime10ms * gARDFFoxDuration10ms/gARDFFoxDuration10ms_corr )/100;
}



int8_t ARDF_Get_GainDiff(void)
{
   return ARDF_ORIG_GAIN_DB - ardf_gain_table[ ARDF_Get_GainIndex(gEeprom.RX_VFO) ].gain_dB;
}



void ARDF_DoGainCheat(void)
{
   uint8_t vfo = gEeprom.RX_VFO;
   uint32_t frequency = 0;

   if ( ARDF_ActiveGainCheatType(vfo) == ARDF_INT_LNA_OFF )
   {
      // disable internal lna
      BK4819_ToggleGpioOut(BK4819_GPIO4_PIN32_VHF_LNA, false);
      BK4819_ToggleGpioOut(BK4819_GPIO3_PIN31_UHF_LNA, false);
      return;      
   }
   else if ( ARDF_ActiveGainCheatType(vfo) == ARDF_HARMONIC_2 )
   {
      // 2. harmonic
      frequency = (gARDFGainCheatBaseFrequency[vfo] * 2) / 10;      
   }   
   else if ( ARDF_ActiveGainCheatType(vfo) == ARDF_HARMONIC_3 )
   {
      // 3. harmonic
      frequency = (gARDFGainCheatBaseFrequency[vfo] * 3) / 10;      
   }   

   if ( RX_freq_check(frequency) < 0 )
   {
      // frequency not allowed
      gARDFPlayEndBeep = true;
      AUDIO_PlayBeep( BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL );
      gARDFPlayEndBeep = false;

      return;
   }


   gTxVfo->freq_config_RX.Frequency = frequency;
   BK4819_SetFrequency(frequency);
   // not gRequestSaveChannel = 1 because gain cheat must not be saved!

   uint16_t reg = BK4819_ReadRegister(BK4819_REG_30);
   BK4819_WriteRegister(BK4819_REG_30, reg & ~BK4819_REG_30_ENABLE_VCO_CALIB);
   BK4819_WriteRegister(BK4819_REG_30, reg);

   BK4819_PickRXFilterPathBasedOnFrequency(frequency);

   return;
}



void ARDF_UndoGainCheat(void)
{
   uint8_t vfo = gEeprom.RX_VFO;
   uint32_t frequency = 0;

   if ( ARDF_ActiveGainCheatType(vfo) == ARDF_INT_LNA_OFF )
   {
      // reactivate LNA
      BK4819_PickRXFilterPathBasedOnFrequency(gARDFGainCheatBaseFrequency[vfo] / 10);
      return;
   }
   else if ( (ARDF_ActiveGainCheatType(vfo) == ARDF_HARMONIC_2) || (ARDF_ActiveGainCheatType(vfo) == ARDF_HARMONIC_3) )
   {
      // undo harmonic
      frequency = gARDFGainCheatBaseFrequency[vfo] / 10;
   }
   
   if ( RX_freq_check(frequency) < 0 )
   {
      // frequency not allowed
      gARDFPlayEndBeep = true;
      AUDIO_PlayBeep( BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL );
      gARDFPlayEndBeep = false;

      return;
   }
   gTxVfo->freq_config_RX.Frequency = frequency;
   BK4819_SetFrequency(frequency);
   // not gRequestSaveChannel = 1 because gain cheat must not be saved!

   uint16_t reg = BK4819_ReadRegister(BK4819_REG_30);
   BK4819_WriteRegister(BK4819_REG_30, reg & ~BK4819_REG_30_ENABLE_VCO_CALIB);
   BK4819_WriteRegister(BK4819_REG_30, reg);

   BK4819_PickRXFilterPathBasedOnFrequency(frequency);

   return;

}



void ARDF_StopGainCheatFox(void)
{
   // stop gain cheat if active for the current fox

   uint8_t vfo = gEeprom.RX_VFO;
   uint8_t activefox = gARDFActiveFox;

   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }

   if ( (gSetting_ARDFEnable) && (ARDF_ActiveGainCheatType(vfo) != ARDF_NO_GAIN_CHEAT) )
   {
      // gain cheat active. disable.
      ARDF_UndoGainCheat();

      ardf_type_gain_cheat[vfo][activefox] = ARDF_NO_GAIN_CHEAT;
   }

   return;
}



void ARDF_StopGainCheatVfo(void)
{
   // stop gain cheat if active for the current vfo

   uint8_t vfo = gEeprom.RX_VFO;

   if ( (gSetting_ARDFEnable) && (ARDF_ActiveGainCheatType(vfo) != ARDF_NO_GAIN_CHEAT) )
   {
      // gain cheat active at the moment. disable it.
      ARDF_UndoGainCheat();
   }

   for (int i = 0; i < ARDF_NUM_FOX_MAX; i++ )
   {
      // disable gain cheat on this vfo
      ardf_type_gain_cheat[vfo][i] = ARDF_NO_GAIN_CHEAT;
   }

   return;
}




void ARDF_DisableGainCheat(void)
{
   // disable any gain cheat

   uint8_t vfo = gEeprom.RX_VFO;

   if ( (gSetting_ARDFEnable) && (ARDF_ActiveGainCheatType(vfo) != ARDF_NO_GAIN_CHEAT) )
   {
      // gain cheat currently active. stop it.
      ARDF_UndoGainCheat();
   }

   for ( int i = 0; i < ARDF_NUM_FOX_MAX; i++ )
   {
      // disable gain cheat completely
      ardf_type_gain_cheat[0][i] = ARDF_NO_GAIN_CHEAT;
      ardf_type_gain_cheat[1][i] = ARDF_NO_GAIN_CHEAT;
   }

   return;
}



t_ardf_gain_cheat_type ARDF_ActiveGainCheatType(uint8_t vfo)
{
   // get gain cheat type of active fox for given vfo

   uint8_t activefox = gARDFActiveFox;
   
   if ( ARDF_ActVfoHasGainRemember(vfo) == false )
   {
      // do not remember fox gains on this vfo
      activefox = 0;
   }

   return ardf_type_gain_cheat[vfo][activefox];

}



#endif
