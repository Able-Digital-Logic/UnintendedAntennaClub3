/**
 * @file    ui.c
 * @brief   Display UI – power-on logo, main menu, and sub-screens.
 *
 * Button layout (configurable in ui.h):
 *   BtnA  →  scroll UP   / previous item
 *   BtnB  →  scroll DOWN / next item
 *   BtnC  →  CONFIRM / select highlighted item  (also: back from sub-screens)
 *
 * Call order:
 *   1. Displ_Init(...)   – initialise the hardware driver
 *   2. UI_Init()         – show power-on screen
 *   3. UI_Update(btns)   – call every ~20 ms from main loop
 */

#include "ui.h"
#include "string.h"
#include "stdio.h"
#include "z_displ_ST7735.h"
#include "z_displ_ST7735_test.h"

/* ═══════════════════════════════════════════════════════════════
 *  Internal state
 * ═══════════════════════════════════════════════════════════════ */

static UI_Screen_e  s_currentScreen   = SCREEN_POWER_ON;
static uint8_t      s_menuIndex       = 0;       /* highlighted menu item  */
static uint32_t     s_tickCounter     = 0;       /* simple tick counter    */
static uint8_t      s_lastButtons     = BTN_NONE;
static uint8_t      s_screenNeedsRedraw = 1;
static uint8_t      s_testRunning     = 0;       /* 1 while Displ_TestAll() is executing */

/* Power-on splash duration in UI_Update() ticks (~20 ms each → 150 = 3 s) */
#define SPLASH_TICKS  150
#define FOOTER_Y   (LCD_H - 14)
/* ═══════════════════════════════════════════════════════════════
 *  Menu item labels
 * ═══════════════════════════════════════════════════════════════ */
static const char *MENU_LABELS[MENU_ITEM_COUNT] = {
    "New Recording",
    "Past Recordings",
    "Play Test File",
};

/* ═══════════════════════════════════════════════════════════════
 *  Forward declarations
 * ═══════════════════════════════════════════════════════════════ */
static void Draw_PowerOn(void);
static void Draw_MainMenu(void);
static void Draw_MenuItem(uint8_t index, uint8_t selected);
static void Draw_NewRecording(void);
static void Draw_PastRecordings(void);
static void Draw_PlayTestFile(void);
static void Draw_Header(const char *title);
static void Draw_Footer(const char *hintA, const char *hintB, const char *hintC);
static uint8_t Button_Pressed(uint8_t current, uint8_t last, uint8_t btn);

/* ═══════════════════════════════════════════════════════════════
 *  Public API
 * ═══════════════════════════════════════════════════════════════ */

void UI_Init(void)
{
    s_currentScreen    = SCREEN_POWER_ON;
    s_menuIndex        = 0;
    s_tickCounter      = 0;
    s_lastButtons      = BTN_NONE;
    s_screenNeedsRedraw = 1;

    Draw_PowerOn();
}

/* ─────────────────────────────────────────────────────────────── */
void UI_Update(uint8_t buttons)
{
    s_tickCounter++;

    /* ── Power-on splash: auto-advance after SPLASH_TICKS ── */
    if (s_currentScreen == SCREEN_POWER_ON)
    {
        if (s_tickCounter >= SPLASH_TICKS ||
            Button_Pressed(buttons, s_lastButtons, BTN_C))
        {
            UI_GoTo(SCREEN_MAIN_MENU);
        }
        s_lastButtons = buttons;
        return;
    }

    /* ── Detect fresh button presses (edge, not level) ── */
    uint8_t pressedA = Button_Pressed(buttons, s_lastButtons, BTN_A);
    uint8_t pressedB = Button_Pressed(buttons, s_lastButtons, BTN_B);
    uint8_t pressedC = Button_Pressed(buttons, s_lastButtons, BTN_C);
    s_lastButtons = buttons;

    /* ── Main Menu navigation ── */
    if (s_currentScreen == SCREEN_MAIN_MENU)
    {
        if (pressedA)   /* scroll up */
        {
            uint8_t prev = s_menuIndex;
            s_menuIndex  = (s_menuIndex == 0) ? (MENU_ITEM_COUNT - 1)
                                               : (s_menuIndex - 1);
            /* Redraw only the two affected rows for speed */
            Draw_MenuItem(prev,         0);
            Draw_MenuItem(s_menuIndex,  1);
        }
        else if (pressedB)  /* scroll down */
        {
            uint8_t prev = s_menuIndex;
            s_menuIndex  = (s_menuIndex + 1) % MENU_ITEM_COUNT;
            Draw_MenuItem(prev,         0);
            Draw_MenuItem(s_menuIndex,  1);
        }
        else if (pressedC)  /* confirm */
        {
            switch (s_menuIndex)
            {
                case 0: UI_GoTo(SCREEN_NEW_RECORDING);   break;
                case 1: UI_GoTo(SCREEN_PAST_RECORDINGS); break;
                case 2: UI_GoTo(SCREEN_PLAY_TEST_FILE);  break;
                default: break;
            }
        }
        return;
    }

    /* ── PLAY TEST FILE screen ── */
    if (s_currentScreen == SCREEN_PLAY_TEST_FILE)
    {
        if (s_testRunning)
        {
            /* Displ_TestAll() is blocking – we reach here only after it
             * has returned.  Immediately go back to the main menu.      */
            s_testRunning = 0;
            UI_GoTo(SCREEN_MAIN_MENU);
        }
        else if (pressedC)
        {
            /* Show "Running…" feedback, then execute the test.
             * Because Displ_TestAll() is synchronous / blocking, the
             * call below will not return until the full test is done.
             * UI_Update() is re-entered on the very next tick after
             * that, at which point s_testRunning == 1 triggers the
             * branch above and we jump straight to the main menu.      */
            s_testRunning = 1;
            Draw_PlayTestFile();        /* redraws with "Running…" text  */
            Displ_TestAll();            /* ← blocking – runs full test   */
            /* Displ_TestAll() returns here; next UI_Update tick cleans up */
        }
        /* BtnA / BtnB intentionally ignored while test is running */
        return;
    }

    /* ── All other sub-screens: BtnC returns to main menu ── */
    if (pressedC)
    {
        UI_GoTo(SCREEN_MAIN_MENU);
    }

    /* ── Add sub-screen-specific button handling below ── */
    /* Example: BtnA / BtnB could scroll a list of past recordings, etc. */
}

/* ─────────────────────────────────────────────────────────────── */
void UI_GoTo(UI_Screen_e screen)
{
    s_currentScreen     = screen;
    s_tickCounter       = 0;
    s_screenNeedsRedraw = 1;

    switch (screen)
    {
        case SCREEN_POWER_ON:        Draw_PowerOn();         break;
        case SCREEN_MAIN_MENU:       Draw_MainMenu();        break;
        case SCREEN_NEW_RECORDING:   Draw_NewRecording();    break;
        case SCREEN_PAST_RECORDINGS: Draw_PastRecordings();  break;
        case SCREEN_PLAY_TEST_FILE:
            s_testRunning = 0;          /* always start in idle state */
            Draw_PlayTestFile();
            break;
        default:                     Draw_MainMenu();        break;
    }
}

/* ─────────────────────────────────────────────────────────────── */
UI_Screen_e UI_CurrentScreen(void)
{
    return s_currentScreen;
}

/* ═══════════════════════════════════════════════════════════════
 *  Screen renderers
 * ═══════════════════════════════════════════════════════════════ */

/**
 * POWER-ON SPLASH
 * ┌──────────────────────────┐
 * │                          │
 * │   ████  (logo circle)    │
 * │                          │
 * │      MY DEVICE           │
 * │    Audio Recorder        │
 * │                          │
 * │   [ Press C to start ]   │
 * └──────────────────────────┘
 */
static void Draw_PowerOn(void)
{
    Displ_CLS(COLOR_BG);

    /* Decorative outer ring */
    Displ_drawCircle(LCD_W / 2, 55, 30, COLOR_ACCENT);
    Displ_drawCircle(LCD_W / 2, 55, 27, COLOR_ACCENT);

    /* Inner filled circle */
    Displ_fillCircle(LCD_W / 2, 55, 22, COLOR_ACCENT);

    /* Device initials centred in circle  */
    Displ_CString(LCD_W/2 - 22, 44, LCD_W/2 + 22, 66,
                  "REC", Font16, 1, COLOR_BG, COLOR_ACCENT);

    /* Product name */
    Displ_CString(0, 95, LCD_W, 111,
                  "MY DEVICE", Font16, 1, COLOR_ACCENT, COLOR_BG);

    /* Subtitle */
    Displ_CString(0, 113, LCD_W, 125,
                  "Audio Recorder", Font12, 1, COLOR_SUBTITLE, COLOR_BG);

    /* Prompt */
    Displ_CString(0, 143, LCD_W, 155,
                  "Press C to start", Font8, 1, COLOR_DIM, COLOR_BG);

    /* Bottom accent line */
    Displ_Line(10, 157, LCD_W - 10, 157, COLOR_ACCENT);
}

/* ─────────────────────────────────────────────────────────────── */
/**
 * MAIN MENU
 * ┌──────────────────────────┐
 * │ ═══  MAIN MENU  ════════ │  ← header
 * │                          │
 * │  ► New Recording         │  ← items (one highlighted)
 * │    Past Recordings       │
 * │    Play Test File        │
 * │                          │
 * │ A:▲  B:▼  C:Select       │  ← footer hints
 * └──────────────────────────┘
 */
static void Draw_MainMenu(void)
{
    Displ_CLS(COLOR_BG);
    Draw_Header("MAIN MENU");

    for (uint8_t i = 0; i < MENU_ITEM_COUNT; i++)
    {
        Draw_MenuItem(i, (i == s_menuIndex));
    }

    Draw_Footer("Up", "Down", "Select");
}

/* ─────────────────────────────────────────────────────────────── */
/* Menu item geometry */
#define MENU_ITEM_Y_START  34    /* y of first item top edge       */
#define MENU_ITEM_HEIGHT   30    /* height of each item row         */
#define MENU_ITEM_PADDING   4    /* inner vertical text padding     */

static void Draw_MenuItem(uint8_t index, uint8_t selected)
{
    int16_t y = MENU_ITEM_Y_START + index * MENU_ITEM_HEIGHT;

    uint16_t bg  = selected ? COLOR_MENU_SEL_BG  : COLOR_MENU_IDLE_BG;
    uint16_t fg  = selected ? COLOR_MENU_SEL_FG  : COLOR_MENU_IDLE_FG;

    /* Background fill */
    Displ_FillArea(4, y, LCD_W - 8, MENU_ITEM_HEIGHT - 2, bg);

    /* Rounded border on selected item */
    if (selected)
    {
        Displ_drawRoundRect(4, y, LCD_W - 8, MENU_ITEM_HEIGHT - 2,
                            4, COLOR_BORDER);
    }

    /* Arrow indicator */
    if (selected)
    {
        Displ_WChar(7, y + MENU_ITEM_PADDING + 2, '>', Font12, 1,
                    fg, bg);
    }

    /* Label – centred horizontally within the row */
    Displ_CString(16, y + MENU_ITEM_PADDING,
                  LCD_W - 4, y + MENU_ITEM_PADDING + 16,
                  MENU_LABELS[index], Font12, 1, fg, bg);
}

/* ─────────────────────────────────────────────────────────────── */
/**
 * NEW RECORDING screen  (placeholder – customise as needed)
 */
static void Draw_NewRecording(void)
{
    Displ_CLS(COLOR_BG);
    Draw_Header("NEW RECORDING");

    /* Recording indicator circle */
    Displ_fillCircle(LCD_W / 2, 80, 18, 0xF800);   /* red dot */
    Displ_drawCircle(LCD_W / 2, 80, 21, 0xF800);

    Displ_CString(0, 106, LCD_W, 120,
                  "Ready to Record", Font12, 1, COLOR_WHITE, COLOR_BG);

    Displ_CString(0, 122, LCD_W, 134,
                  "Press C to Begin", Font8, 1, COLOR_SUBTITLE, COLOR_BG);

    Draw_Footer("--", "--", "Back");
}

/* ─────────────────────────────────────────────────────────────── */
/**
 * PAST RECORDINGS screen  (placeholder – populate with file list)
 */
static void Draw_PastRecordings(void)
{
    Displ_CLS(COLOR_BG);
    Draw_Header("PAST RECORDINGS");

    /* Placeholder – replace with real file list rendering */
    Displ_CString(0, 70, LCD_W, 84,
                  "No recordings", Font12, 1, COLOR_SUBTITLE, COLOR_BG);

    Displ_CString(0, 88, LCD_W, 100,
                  "found on SD card", Font8, 1, COLOR_DIM, COLOR_BG);

    /* SD card icon (simple rectangle representation) */
    Displ_drawRoundRect(LCD_W/2 - 14, 42, 28, 22, 2, COLOR_ACCENT);
    Displ_FillArea(LCD_W/2 - 14, 42, 4, 8, COLOR_ACCENT);
    Displ_FillArea(LCD_W/2 - 6,  42, 4, 8, COLOR_ACCENT);
    Displ_FillArea(LCD_W/2 + 2,  42, 4, 8, COLOR_ACCENT);

    Draw_Footer("Up", "Down", "Back");
}

/* ─────────────────────────────────────────────────────────────── */
/**
 * PLAY TEST FILE screen
 *   Idle state    – shows play triangle and "Press C to Play"
 *   Running state – shows spinner text and "Running…" while Displ_TestAll() executes
 */
static void Draw_PlayTestFile(void)
{
    Displ_CLS(COLOR_BG);
    Draw_Header("PLAY TEST FILE");

    if (s_testRunning)
    {
        /* ── Running state ── */
        /* Animated-style hourglass made from two triangles */
        Displ_fillTriangle(LCD_W/2 - 14, 52,
                           LCD_W/2 + 14, 52,
                           LCD_W/2,      72, COLOR_ACCENT);
        Displ_fillTriangle(LCD_W/2 - 14, 92,
                           LCD_W/2 + 14, 92,
                           LCD_W/2,      72, COLOR_DIM);
        Displ_drawRoundRect(LCD_W/2 - 15, 51, 30, 43, 2, COLOR_ACCENT);

        Displ_CString(0, 102, LCD_W, 116,
                      "Running Test...", Font12, 1, COLOR_ACCENT, COLOR_BG);

        Displ_CString(0, 118, LCD_W, 130,
                      "Please wait", Font8, 1, COLOR_SUBTITLE, COLOR_BG);

        /* No footer – buttons are locked during the test */
        Displ_Line(0, FOOTER_Y - 2, LCD_W, FOOTER_Y - 2, COLOR_DIM);
        Displ_CString(0, FOOTER_Y, LCD_W, LCD_H,
                      "Buttons locked", Font8, 1, COLOR_DIM, COLOR_BG);
    }
    else
    {
        /* ── Idle state ── */
        /* Simple play-button triangle */
        Displ_fillTriangle(LCD_W/2 - 12, 60,
                           LCD_W/2 - 12, 88,
                           LCD_W/2 + 16, 74,
                           COLOR_ACCENT);

        Displ_CString(0, 100, LCD_W, 114,
                      "Display Test", Font12, 1, COLOR_WHITE, COLOR_BG);

        Displ_CString(0, 116, LCD_W, 128,
                      "Press C to Run", Font8, 1, COLOR_SUBTITLE, COLOR_BG);

        Draw_Footer("--", "--", "Run");
    }
}

/* ═══════════════════════════════════════════════════════════════
 *  Shared UI chrome helpers
 * ═══════════════════════════════════════════════════════════════ */

/**
 * @brief  Draw a filled header bar with centred title text.
 */
static void Draw_Header(const char *title)
{
    /* Filled bar */
    Displ_FillArea(0, 0, LCD_W, 28, COLOR_ACCENT);

    /* Title text */
    Displ_CString(0, 6, LCD_W, 22, title, Font16, 1,
                  COLOR_BLACK, COLOR_ACCENT);
}

/**
 * @brief  Draw a three-button hint footer at the bottom of the screen.
 *         Pass "--" to skip a button label.
 */


static void Draw_Footer(const char *hintA, const char *hintB,
                        const char *hintC)
{
    /* Separator line */
    Displ_Line(0, FOOTER_Y - 2, LCD_W, FOOTER_Y - 2, COLOR_DIM);

    /* Three equal-width zones */
    uint16_t zoneW = LCD_W / 3;

    if (hintA[0] != '-')
    {
        char buf[10];
        snprintf(buf, sizeof(buf), "A:%s", hintA);
        Displ_CString(0,          FOOTER_Y, zoneW,      LCD_H,
                      buf, Font8, 1, COLOR_DIM, COLOR_BG);
    }
    if (hintB[0] != '-')
    {
        char buf[10];
        snprintf(buf, sizeof(buf), "B:%s", hintB);
        Displ_CString(zoneW,      FOOTER_Y, zoneW * 2,  LCD_H,
                      buf, Font8, 1, COLOR_DIM, COLOR_BG);
    }
    if (hintC[0] != '-')
    {
        char buf[10];
        snprintf(buf, sizeof(buf), "C:%s", hintC);
        Displ_CString(zoneW * 2,  FOOTER_Y, LCD_W,      LCD_H,
                      buf, Font8, 1, COLOR_DIM, COLOR_BG);
    }
}

/* ═══════════════════════════════════════════════════════════════
 *  Input helper
 * ═══════════════════════════════════════════════════════════════ */

/**
 * @brief  Returns 1 on the rising edge of `btn` (was not pressed,
 *         is now pressed).  Provides simple debounce via edge detection.
 */
static uint8_t Button_Pressed(uint8_t current, uint8_t last, uint8_t btn)
{
    return ((current & btn) && !(last & btn)) ? 1 : 0;
}
