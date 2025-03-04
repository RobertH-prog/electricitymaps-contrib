import { useAtom } from 'jotai';
import { useTranslation } from 'translation/translation';
import { TimeAverages } from 'utils/constants';
import { formatCo2, scalePower } from 'utils/formatting';
import { getNetExchange, round } from 'utils/helpers';
import { displayByEmissionsAtom, timeAverageAtom } from 'utils/state/atoms';

import { InnerAreaGraphTooltipProps } from '../types';
import AreaGraphToolTipHeader from './AreaGraphTooltipHeader';

export default function NetExchangeChartTooltip({
  zoneDetail,
}: InnerAreaGraphTooltipProps) {
  if (!zoneDetail) {
    return null;
  }
  const [timeAverage] = useAtom(timeAverageAtom);
  const [displayByEmissions] = useAtom(displayByEmissionsAtom);
  const { __ } = useTranslation();

  const isHourly = timeAverage === TimeAverages.HOURLY;
  const { stateDatetime } = zoneDetail;

  const netExchange = getNetExchange(zoneDetail, displayByEmissions);
  const { formattingFactor, unit: powerUnit } = scalePower(netExchange, isHourly);

  const unit = displayByEmissions ? __('ofCO2eq') : powerUnit;
  const value = displayByEmissions
    ? formatCo2(Math.abs(netExchange))
    : Math.abs(round(netExchange / formattingFactor));

  return (
    <div className="w-full rounded-md bg-white p-3 shadow-xl sm:w-[350px] dark:border dark:border-gray-700 dark:bg-gray-800">
      <AreaGraphToolTipHeader
        datetime={new Date(stateDatetime)}
        timeAverage={timeAverage}
        squareColor="#7f7f7f"
        title={__('tooltips.netExchange')}
      />
      <p className="flex justify-center text-base">
        {netExchange >= 0 ? __('tooltips.importing') : __('tooltips.exporting')}{' '}
        <b className="mx-1">{value}</b> {unit}
      </p>
    </div>
  );
}
