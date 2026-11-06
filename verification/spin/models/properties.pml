/* Select exactly one CHK_* via the runner. No monitor changes controller state. */
byte observed = 0;
byte previous = 0;
byte last_green = 0;
int green_age = 0;
byte yellow_age = 0;
int ns_wait = 0;
int ew_wait = 0;
#define WAIT_LIMIT (MAX_GREEN + 2 * YELLOW_TIME)

#ifdef CHK_L2
#ifndef AGENT_FAIRNESS
#define AGENT_FAIRNESS 0
#endif
bool request_event = false;
int requested_action = 0;
bool request_eligible = false;

inline record_request() {
    d_step {
        requested_action = action;
        request_eligible = (phase_duration >= MIN_GREEN);
        request_event = true;
        printf("REQUEST %d %d\n", requested_action, request_eligible)
    }
}
#endif

inline observe_second() {
#ifdef CHK_L2
    observed = signal;
#endif
#ifdef CHK_S1
    /* Network preflight validates the protected-link interpretation of each code. */
    assert(signal <= 3);
    assert(!((signal == 0) && (signal == 2)));
#endif
#ifdef CHK_T1
    assert(!((previous == 0 && signal == 2) ||
             (previous == 2 && signal == 0)));
    previous = signal;
#endif
#ifdef CHK_T2
    if
    :: (previous == 1 || previous == 3) && (signal == 0 || signal == 2) ->
        assert(yellow_age >= 3);
        assert(signal != last_green)
    :: else -> skip
    fi;
    if
    :: signal == 0 || signal == 2 ->
        last_green = signal;
        yellow_age = 0
    :: else ->
        if
        :: yellow_age < 3 -> yellow_age++
        :: else -> skip
        fi
    fi;
    previous = signal;
    observed = signal;
#endif
#ifdef CHK_G1
    if
    :: (previous == 0 || previous == 2) && signal != previous ->
        assert(green_age >= MIN_GREEN)
    :: else -> skip
    fi;
    if
    :: signal == 0 || signal == 2 ->
        if
        :: signal != previous -> green_age = 1
        :: else ->
            if
            :: green_age < MIN_GREEN + 1 -> green_age++
            :: else -> skip
            fi
        fi
    :: else -> green_age = 0
    fi;
    previous = signal;
#endif
#ifdef CHK_G2
    if
    :: signal == 0 || signal == 2 ->
        if
        :: signal != previous -> green_age = 1
        :: else ->
            if
            :: green_age < MAX_GREEN + 1 -> green_age++
            :: else -> skip
            fi
        fi
    :: else -> green_age = 0
    fi;
    previous = signal;
    printf("TIMING %d %d %d\n", green_age, ns_wait, ew_wait);
    assert(green_age <= MAX_GREEN);
#endif
#ifdef CHK_L1
    if
    :: signal == 0 -> ns_wait = 0
    :: else ->
        if
        :: ns_wait < WAIT_LIMIT + 1 -> ns_wait++
        :: else -> skip
        fi
    fi;
    if
    :: signal == 2 -> ew_wait = 0
    :: else ->
        if
        :: ew_wait < WAIT_LIMIT + 1 -> ew_wait++
        :: else -> skip
        fi
    fi;
    printf("TIMING %d %d %d\n", green_age, ns_wait, ew_wait);
    assert(ns_wait <= WAIT_LIMIT);
    assert(ew_wait <= WAIT_LIMIT);
#endif
    skip
}

inline check_boundary() {
#ifdef CHK_G2
    /* Shared harness checks controller age in addition to displayed green age. */
    assert(phase_duration <= MAX_GREEN);
#endif
#ifdef CHK_C1
    assert(current_phase == 0 || current_phase == 1);
    assert((current_phase == 0 && signal == 0) ||
           (current_phase == 1 && signal == 2));
#endif
    skip
}

#if defined(CHK_T2) && !defined(TRACE)
/* Duration/opposite-next-green assertions above complement eventual completion.
 * Only the sampled signal changes observed; zero-time yellow is not a sample.
 */
ltl yellow_completion {
    [] ((observed == 1 || observed == 3) ->
        <> (observed == 0 || observed == 2))
}
#endif

#if defined(CHK_L2) && !defined(TRACE)
#define BOTH_SERVICE (([] <> (observed == 0)) && ([] <> (observed == 2)))
#if AGENT_FAIRNESS == 2
#define FAIR_INPUT (([] <> (request_event && requested_action == 0 && request_eligible)) && ([] <> (request_event && requested_action == 1 && request_eligible)))
#elif AGENT_FAIRNESS == 1
#define FAIR_INPUT (([] <> (request_event && requested_action == 0)) && ([] <> (request_event && requested_action == 1)))
#else
#define FAIR_INPUT true
#endif
#ifdef FAIRNESS_FEASIBILITY
/* Deliberately negate the premise: an acceptance cycle witnesses feasibility. */
ltl agent_service { ! FAIR_INPUT }
#else
ltl agent_service { FAIR_INPUT -> BOTH_SERVICE }
#endif
#endif
