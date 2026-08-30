#ifndef __UI_H__
#define __UI_H__

#include "stdint.h"
#include "z_displ_ST7735.h"
#include "fonts.h"

/* ─────────────────────────────────────────────
 *  Display dimensions  (ST7735 typical 128×160)
 * ───────────────────────────────────────────── */
#define LCD_W   128
#define LCD_H   160

/* ─────────────────────────────────────────────
 *  Colour palette  (RGB565)
 * ───────────────────────────────────────────── */
#define COLOR_BLACK         0x0000
#define COLOR_WHITE         0xFFFF
#define COLOR_BG            0x0000   /* screen background            */
#define COLOR_ACCENT        0x07FF   /* cyan  – logo / highlights    */
#define COLOR_MENU_SEL_BG   0x07FF   /* selected item background     */
#define COLOR_MENU_SEL_FG   0x0000   /* selected item text           */
#define COLOR_MENU_IDLE_BG  0x0000   /* unselected item background   */
#define COLOR_MENU_IDLE_FG  0xFFFF   /* unselected item text         */
#define COLOR_BORDER        0x07FF   /* rectangle borders            */
#define COLOR_SUBTITLE      0xC618   /* light-grey subtitle text     */
#define COLOR_DIM           0x4208   /* dim grey                     */

/* ─────────────────────────────────────────────
 *  Button definitions
 *  Map these to your actual GPIO read macros.
 * ───────────────────────────────────────────── */
#define BTN_NONE   0x00
#define BTN_A      0x01   /* e.g. "Up / Select-left"  */
#define BTN_B      0x02   /* e.g. "Down / Navigate"   */
#define BTN_C      0x04   /* e.g. "Confirm / Enter"   */

/* ─────────────────────────────────────────────
 *  UI screen identifiers
 * ───────────────────────────────────────────── */
typedef enum {
    SCREEN_POWER_ON = 0,
    SCREEN_MAIN_MENU,
    SCREEN_NEW_RECORDING,
    SCREEN_PAST_RECORDINGS,
    SCREEN_PLAY_TEST_FILE,
} UI_Screen_e;

/* ─────────────────────────────────────────────
 *  Main-menu item count
 * ───────────────────────────────────────────── */
#define MENU_ITEM_COUNT  3

/* ─────────────────────────────────────────────
 *  Public API
 * ───────────────────────────────────────────── */

/**
 * @brief  Initialise the UI subsystem and show the power-on screen.
 *         Call once after Displ_Init().
 */
void UI_Init(void);

/**
 * @brief  Main UI tick – call from your main loop (or a timer ISR).
 *         Pass the currently pressed button(s) as a BTN_x bitmask,
 *         or BTN_NONE when no button is held.
 *
 * @param  buttons   Bitmask of currently-pressed buttons.
 */
void UI_Update(uint8_t buttons);

/**
 * @brief  Force a transition to a specific screen.
 *         Useful for external events (e.g. recording complete).
 */
void UI_GoTo(UI_Screen_e screen);

/**
 * @brief  Return the currently displayed screen.
 */
UI_Screen_e UI_CurrentScreen(void);

#endif /* __UI_H__ */
