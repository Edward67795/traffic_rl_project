#define MIN_GREEN 10
#define MAX_GREEN 60
#define YELLOW_TIME 3
byte signal=0; int action=0; int phase_duration=0; int current_phase=0;
#include "properties.pml"
init { observed=0; do :: action=0; phase_duration=10; record_request(); signal=0; d_step { observe_second() }; request_event=false;
action=1; phase_duration=10; record_request(); signal=2; d_step { observe_second() }; request_event=false; od }
