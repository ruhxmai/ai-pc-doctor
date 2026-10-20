% =====================================================================
%  Логическая модель знаний: диагностика неисправностей ПК
%  Синтаксис Prolog: факты «p(a, b).», правила «голова :- условие.»
%  Переменные — с заглавной буквы.
% =====================================================================

% ---------- Факты: иерархия понятий «является» ----------
is_a(hdd, storage).
is_a(ssd, storage).
is_a(storage, hardware_component).
is_a(psu, hardware_component).
is_a(cpu, hardware_component).
is_a(ram, hardware_component).
is_a(gpu, hardware_component).
is_a(cooler, hardware_component).
is_a(motherboard, hardware_component).
is_a(hardware_component, device).
is_a(os, software).
is_a(driver, software).

% ---------- Факты: состав «входит в» ----------
part_of(cpu, motherboard).
part_of(ram, motherboard).
part_of(gpu, motherboard).
part_of(motherboard, system_unit).
part_of(psu, system_unit).
part_of(cooler, system_unit).
part_of(storage, system_unit).
part_of(system_unit, computer).
part_of(driver, os).
part_of(os, computer).

% ---------- Факты: какой компонент поражает неисправность ----------
affects(psu_failure, psu).
affects(ram_failure, ram).
affects(overheating, cooler).
affects(disk_failure, storage).
affects(gpu_failure, gpu).
affects(malware, os).
affects(driver_issue, driver).
affects(os_corruption, os).

% ---------- Факты: степень опасности ----------
severity(psu_failure, high).
severity(ram_failure, medium).
severity(overheating, medium).
severity(disk_failure, high).
severity(gpu_failure, medium).
severity(malware, medium).
severity(driver_issue, low).
severity(os_corruption, medium).

% ---------- Правила: транзитивные отношения ----------
kind_of(X, Y) :- is_a(X, Y).
kind_of(X, Z) :- is_a(X, Y), kind_of(Y, Z).

inside(X, Y) :- part_of(X, Y).
inside(X, Z) :- part_of(X, Y), inside(Y, Z).

% ---------- Правила: классификация неисправностей ----------
hardware_fault(F) :- affects(F, C), kind_of(C, hardware_component).
software_fault(F) :- affects(F, C), kind_of(C, software).
in_system_unit(F) :- affects(F, C), inside(C, system_unit).

% ---------- Диагностические правила (неделя 6: AND «,»  OR «;»  NOT «not») ----------
% Признаки пользователя добавляются в базу как факты symptom(...).
% Отрицание работает по гипотезе замкнутого мира: не сообщённый признак считается отсутствующим.

diagnosis(psu_failure) :-
    symptom(no_power), (symptom(fans_not_spin) ; symptom(burning_smell)).
diagnosis(psu_failure) :-
    symptom(random_reboots), symptom(burning_smell).

diagnosis(ram_failure) :-
    symptom(beeps), (symptom(bsod) ; symptom(random_reboots) ; symptom(freezes)),
    not symptom(artifacts_screen).

diagnosis(overheating) :-
    symptom(high_temp), (symptom(random_reboots) ; symptom(loud_fan) ; symptom(slow_work) ; symptom(games_crash)).

diagnosis(disk_failure) :-
    symptom(clicking_sound), (symptom(files_corrupted) ; symptom(slow_work) ; symptom(freezes)).
diagnosis(disk_failure) :-
    symptom(files_corrupted), symptom(boot_failure), not symptom(after_update).

diagnosis(gpu_failure) :-
    symptom(artifacts_screen), not symptom(after_update).
diagnosis(gpu_failure) :-
    symptom(no_image), not symptom(no_power), not symptom(beeps).

diagnosis(malware) :-
    symptom(popups_ads) ; (symptom(high_cpu_idle), symptom(slow_work)).

diagnosis(driver_issue) :-
    symptom(after_update), (symptom(device_not_working) ; symptom(artifacts_screen)).

diagnosis(os_corruption) :-
    symptom(boot_failure), not symptom(clicking_sound), not symptom(no_power).
diagnosis(os_corruption) :-
    symptom(bsod), symptom(after_update), not symptom(device_not_working).

% ---------- Следствия диагноза ----------
needs_service(F) :- diagnosis(F), hardware_fault(F).
urgent(F) :- diagnosis(F), (severity(F, high) ; symptom(burning_smell)).
backup_data :- diagnosis(disk_failure) ; diagnosis(malware) ; diagnosis(os_corruption).
self_repair(F) :- diagnosis(F), not hardware_fault(F).
