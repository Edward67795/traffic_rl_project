/* Select exactly one CHK_* via the runner. No monitor changes controller state. */
byte observed = 0;
byte previous = 0;
byte last_green = 0;
int green_age = 0;
byte yellow_age = 0;

inline observe_second() {
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
    skip
}

inline check_boundary() {
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
