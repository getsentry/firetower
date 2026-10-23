import {useEffect, useRef, type ComponentProps} from 'react';
import {
  DayPicker,
  useDayPicker,
  type Chevron,
  type Day,
  type DayButton,
  type PreviousMonthButton,
  type Root,
  type WeekNumber,
} from 'react-day-picker';
import * as stylex from '@stylexjs/stylex';
import {ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon} from 'lucide-react';

import type {StyledProps} from '../styles/props';
import {background, border, content, fontWeight, radius} from '../styles/tokens.stylex';

import {buttonStyles} from './buttonStyles';

type CalendarOptions<Props> = Props extends unknown
  ? Omit<
      Props,
      'classNames' | 'styles' | 'modifiersClassNames' | 'modifiersStyles' | 'components'
    >
  : never;
type CalendarProps = StyledProps<CalendarOptions<ComponentProps<typeof DayPicker>>> & {
  classNames?: never;
  styles?: never;
  modifiersClassNames?: never;
  modifiersStyles?: never;
  components?: never;
};
const styles = stylex.create({
  root: {width: 'fit-content', padding: 12, backgroundColor: 'transparent'},
  months: {
    display: 'flex',
    gap: 16,
    flexDirection: {default: 'column', '@media (min-width: 768px)': 'row'},
    position: 'relative',
  },
  month: {display: 'flex', flexDirection: 'column', width: '100%', gap: 16},
  nav: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    width: '100%',
    position: 'absolute',
    top: 0,
    insetInline: 0,
    justifyContent: 'space-between',
  },
  navigationButton: {
    height: 32,
    width: 32,
    padding: 0,
    userSelect: 'none',
    opacity: {default: 1, ':disabled': 0.5},
  },
  monthCaption: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: 32,
    width: '100%',
    paddingInline: 32,
  },
  dropdowns: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    fontSize: 14,
    lineHeight: '20px',
    fontWeight: fontWeight.medium,
    justifyContent: 'center',
    height: 32,
    gap: 6,
    color: content.primary,
  },
  dropdownRoot: {
    position: 'relative',
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: border.secondary,
    borderRadius: radius.md,
  },
  dropdown: {
    position: 'absolute',
    inset: 0,
    color: 'transparent',
    backgroundColor: 'transparent',
  },
  captionLabel: {
    userSelect: 'none',
    fontWeight: fontWeight.medium,
    fontSize: 14,
    lineHeight: '20px',
  },
  dropdownLabel: {
    borderRadius: 6,
    paddingLeft: 8,
    paddingRight: 4,
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    height: 32,
  },
  table: {width: '100%', borderCollapse: 'collapse'},
  weekdays: {display: 'flex'},
  weekday: {
    color: content.secondary,
    borderRadius: 6,
    flex: '1',
    fontWeight: 400,
    fontSize: '0.8rem',
    userSelect: 'none',
  },
  week: {display: 'flex', width: '100%', marginTop: 8},
  weekNumberHeader: {userSelect: 'none', width: 32},
  weekNumber: {fontSize: '0.8rem', userSelect: 'none', color: content.secondary},
  weekNumberContent: {
    display: 'flex',
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
  },
  day: {
    position: 'relative',
    width: '100%',
    height: '100%',
    padding: 0,
    textAlign: 'center',
    aspectRatio: '1',
    userSelect: 'none',
  },
  rangeStart: {
    borderStartStartRadius: 6,
    borderEndStartRadius: 6,
    backgroundColor: background.secondary,
  },
  rangeMiddle: {borderRadius: 0, backgroundColor: background.secondary},
  rangeEnd: {
    borderStartEndRadius: 6,
    borderEndEndRadius: 6,
    backgroundColor: background.secondary,
  },
  today: {backgroundColor: background.secondary, borderRadius: 6},
  selectedToday: {borderRadius: 0},
  outside: {color: content.disabled},
  disabled: {color: content.disabled, opacity: 0.5},
  hidden: {visibility: 'hidden'},
  icon: {width: 16, height: 16},
  dropdownIcon: {width: 14, height: 14},
  rtlIcon: {transform: 'rotate(180deg)'},
  unavailable: {opacity: 0.5},
  dayButton: {
    display: 'flex',
    aspectRatio: '1',
    width: '100%',
    height: 'auto',
    minWidth: 32,
    flexDirection: 'column',
    gap: 4,
    lineHeight: 1,
    fontWeight: 400,
  },
  selected: {
    backgroundColor: background.accentVibrant,
    color: content.onVibrantLight,
    borderRadius: radius.md,
  },
  middleButton: {color: content.primary, backgroundColor: 'transparent', borderRadius: 0},
  firstSelected: {borderStartStartRadius: 6, borderEndStartRadius: 6},
  lastSelected: {borderStartEndRadius: 6, borderEndEndRadius: 6},
});

function Calendar({
  style,
  showOutsideDays = true,
  captionLayout = 'label',
  formatters,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      {...props}
      {...stylex.props(styles.root, style)}
      showOutsideDays={showOutsideDays}
      captionLayout={captionLayout}
      formatters={{
        formatMonthDropdown: date => date.toLocaleString('default', {month: 'short'}),
        ...formatters,
      }}
      classNames={{
        months: stylex.props(styles.months).className,
        month: stylex.props(styles.month).className,
        nav: stylex.props(styles.nav).className,
        month_caption: stylex.props(styles.monthCaption).className,
        dropdowns: stylex.props(styles.dropdowns).className,
        dropdown_root: stylex.props(styles.dropdownRoot).className,
        dropdown: stylex.props(styles.dropdown).className,
        caption_label: stylex.props(
          styles.captionLabel,
          captionLayout !== 'label' && styles.dropdownLabel
        ).className,
        month_grid: stylex.props(styles.table).className,
        weekdays: stylex.props(styles.weekdays).className,
        weekday: stylex.props(styles.weekday).className,
        week: stylex.props(styles.week).className,
        week_number_header: stylex.props(styles.weekNumberHeader).className,
        week_number: stylex.props(styles.weekNumber).className,
      }}
      components={{
        Root: CalendarRoot,
        PreviousMonthButton: CalendarNavigationButton,
        NextMonthButton: CalendarNavigationButton,
        Day: CalendarDay,
        DayButton: CalendarDayButton,
        Chevron: CalendarChevron,
        WeekNumber: CalendarWeekNumber,
      }}
    />
  );
}

function CalendarRoot({rootRef, ...props}: ComponentProps<typeof Root>) {
  return <div data-slot="calendar" ref={rootRef} {...props} />;
}

function CalendarNavigationButton(props: ComponentProps<typeof PreviousMonthButton>) {
  return (
    <button
      {...props}
      {...stylex.props(
        buttonStyles({variant: 'icon', size: 'icon'}),
        styles.navigationButton,
        !!props['aria-disabled'] && styles.unavailable
      )}
    />
  );
}

function CalendarChevron({orientation}: ComponentProps<typeof Chevron>) {
  const {dayPickerProps} = useDayPicker();
  const Icon =
    orientation === 'left'
      ? ChevronLeftIcon
      : orientation === 'right'
        ? ChevronRightIcon
        : ChevronDownIcon;
  return (
    <Icon
      {...stylex.props(
        orientation === 'left' || orientation === 'right'
          ? styles.icon
          : styles.dropdownIcon,
        dayPickerProps.dir === 'rtl' &&
          (orientation === 'left' || orientation === 'right') &&
          styles.rtlIcon
      )}
    />
  );
}

function CalendarWeekNumber({
  children,
  week,
  ...props
}: ComponentProps<typeof WeekNumber>) {
  return (
    <th {...props} data-week-number={week.weekNumber}>
      <div {...stylex.props(styles.weekNumberContent)}>{children}</div>
    </th>
  );
}

function CalendarDay({day, modifiers, ...props}: ComponentProps<typeof Day>) {
  return (
    <td
      {...props}
      data-day={day.isoDate}
      {...stylex.props(
        styles.day,
        modifiers.range_start && styles.rangeStart,
        modifiers.range_middle && styles.rangeMiddle,
        modifiers.range_end && styles.rangeEnd,
        modifiers.today && styles.today,
        modifiers.today && modifiers.selected && styles.selectedToday,
        modifiers.outside && styles.outside,
        modifiers.disabled && styles.disabled,
        modifiers.hidden && styles.hidden
      )}
    />
  );
}

function CalendarDayButton({day, modifiers, ...props}: ComponentProps<typeof DayButton>) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (modifiers.focused) ref.current?.focus();
  }, [modifiers.focused]);
  const {dayPickerProps} = useDayPicker();
  const weekStartsOn =
    dayPickerProps.ISOWeek || dayPickerProps.broadcastCalendar
      ? 1
      : (dayPickerProps.weekStartsOn ??
        dayPickerProps.locale?.options?.weekStartsOn ??
        0);
  const firstInWeek = day.date.getDay() === weekStartsOn;
  const lastInWeek = day.date.getDay() === (weekStartsOn + 6) % 7;
  return (
    <button
      {...props}
      ref={ref}
      {...stylex.props(
        buttonStyles({variant: 'icon', size: 'icon'}),
        styles.dayButton,
        modifiers.selected && styles.selected,
        modifiers.range_middle && styles.middleButton,
        modifiers.selected && firstInWeek && styles.firstSelected,
        modifiers.selected && lastInWeek && styles.lastSelected
      )}
    />
  );
}

export {Calendar};
