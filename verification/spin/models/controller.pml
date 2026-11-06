/* v0 control-flow model. Shared checks are selected by CHK_* macros.
 * Signal codes: 0 NS, 1 NS yellow, 2 EW, 3 EW yellow.
 * See MODEL_MAPPING.md for time sampling and the finite age abstraction.
 */
#ifndef DELTA_TIME
#define DELTA_TIME 5
#endif
#ifndef YELLOW_TIME
#define YELLOW_TIME 3
#endif
#ifndef MIN_GREEN
#define MIN_GREEN 10
#endif
#ifndef MAX_GREEN
#define MAX_GREEN 60
#endif
#ifndef STATIC_PROGRAM
#define STATIC_PROGRAM 0
#endif
#define AGE_CAP (MAX_GREEN + MIN_GREEN + DELTA_TIME + 1)

byte signal = 0;
int current_phase = 0;
int phase_duration = 0;
bool online = false;
byte sp_index = 0;
byte sp_left = 43;
int remaining;
#ifdef TRACE
int elapsed = 0;
int decision = 0;
#endif
int action;

#include "properties.pml"

#ifdef TRACE
/* Generated only by the finite trace checker, never by property verification. */
#include "actions.pml"
#else
inline choose_action() {
    if
    :: action = 0
    :: action = 1
#ifdef ANY_ACTION
    :: action = -1
    :: action = 2
#endif
    fi
}
#endif

inline increment_age() {
    if
    :: phase_duration < AGE_CAP -> phase_duration++
    :: else -> skip
    fi
}

inline tick() {
    d_step {
#ifdef TRACE
        printf("TICK %d %d %d %d %d %d %d\n", elapsed, signal,
               current_phase, phase_duration, online, sp_index, sp_left);
        elapsed++;
#endif
        printf("OBS %d %d %d %d %d\n", signal, current_phase,
               phase_duration, green_age, yellow_age);
        observe_second();
#if STATIC_PROGRAM
        if
        :: !online ->
            sp_left--;
            if
            :: sp_left == 0 ->
                sp_index = (sp_index + 1) % 4;
                signal = sp_index;
                if
                :: sp_index == 0 || sp_index == 2 -> sp_left = 42
                :: else -> sp_left = 3
                fi
            :: else -> skip
            fi
        :: else -> skip
        fi;
#else
        skip;
#endif
    }
}

inline show_yellow() {
    d_step {
        if
        :: signal == 0 || signal == 1 -> signal = 1
        :: else -> signal = 3
        fi;
        online = true
    }
}

inline show_green() {
    d_step {
        /* _set_phase falls back to NS even when current_phase becomes invalid. */
        if
        :: action == 1 -> signal = 2
        :: else -> signal = 0
        fi;
        online = true;
        current_phase = action;
        phase_duration = 0
    }
}

inline report_boundary() {
#ifdef TRACE
    printf("DONE %d %d %d %d %d %d %d %d\n", decision, elapsed, signal,
           current_phase, phase_duration, online, sp_index, sp_left)
#else
    skip
#endif
}

init {
    /* Supported model domain, not validation performed by the original v0. */
    assert(DELTA_TIME > 0 && YELLOW_TIME >= 0);
    assert(MIN_GREEN >= 0 && MAX_GREEN >= 1);
    remaining = 10;
    do
    :: remaining > 0 -> tick(); remaining--
    :: else -> break
    od;
    report_boundary();
    do
#ifdef TRACE
    :: decision >= N_ACTIONS -> break
    :: else ->
#else
    ::
#endif
        choose_action();
#ifdef CHK_L2
        record_request();
#endif
        printf("ACTION %d\n", action);
#ifdef TRACE
        decision++;
#endif
        if
        :: action != current_phase && phase_duration >= MIN_GREEN ->
            show_yellow();
            remaining = YELLOW_TIME;
            do
            :: remaining > 0 -> tick(); remaining--
            :: else -> break
            od;
            show_green()
        :: else -> skip
        fi;
        remaining = DELTA_TIME;
        do
        :: remaining > 0 -> tick(); increment_age(); remaining--
        :: else -> break
        od;
        report_boundary();
        check_boundary()
#ifdef CHK_L2
        ; request_event = false
#endif
    od
}
