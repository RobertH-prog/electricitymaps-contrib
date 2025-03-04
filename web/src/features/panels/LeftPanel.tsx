import * as Sentry from '@sentry/react';
import { TimeDisplay } from 'components/TimeDisplay';
import Logo from 'features/header/Logo';
import { useAtom } from 'jotai';
import { HiChevronLeft, HiChevronRight } from 'react-icons/hi2';
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { useTranslation } from 'translation/translation';

import { leftPanelOpenAtom } from './panelAtoms';
import RankingPanel from './ranking-panel/RankingPanel';
import ZoneDetails from './zone/ZoneDetails';

function HandleLegacyRoutes() {
  const [searchParameters] = useSearchParams();

  const page = (searchParameters.get('page') || 'map')
    .replace('country', 'zone')
    .replace('highscore', 'ranking');
  searchParameters.delete('page');

  const zoneId = searchParameters.get('countryCode');
  searchParameters.delete('countryCode');

  return (
    <Navigate
      to={{
        pathname: zoneId ? `/zone/${zoneId}` : `/${page}`,
        search: searchParameters.toString(),
      }}
    />
  );
}

function ValidZoneIdGuardWrapper({ children }: { children: JSX.Element }) {
  const [searchParameters] = useSearchParams();
  const { zoneId } = useParams();

  if (!zoneId) {
    return <Navigate to="/" replace />;
  }

  // Handle legacy Australia zone names
  if (zoneId.startsWith('AUS')) {
    return (
      <Navigate to={`/zone/${zoneId.replace('AUS', 'AU')}?${searchParameters}`} replace />
    );
  }
  const upperCaseZoneId = zoneId.toUpperCase();
  if (zoneId !== upperCaseZoneId) {
    return <Navigate to={`/zone/${upperCaseZoneId}?${searchParameters}`} replace />;
  }

  return children;
}

type CollapseButtonProps = {
  isCollapsed: boolean;
  onCollapse: () => void;
};

function CollapseButton({ isCollapsed, onCollapse }: CollapseButtonProps) {
  const { __ } = useTranslation();
  return (
    <button
      data-test-id="left-panel-collapse-button"
      className={
        'absolute left-full top-2 z-10 h-12 w-6 cursor-pointer rounded-r bg-zinc-50 pl-1 shadow-[6px_2px_10px_-3px_rgba(0,0,0,0.1)] hover:bg-zinc-100 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800'
      }
      onClick={onCollapse}
      aria-label={
        isCollapsed ? __('aria.label.showSidePanel') : __('aria.label.hideSidePanel')
      }
    >
      {isCollapsed ? <HiChevronRight /> : <HiChevronLeft />}
    </button>
  );
}

function MobileHeader() {
  return (
    <div className="flex w-full items-center justify-between p-1 pt-[env(safe-area-inset-top)] shadow-md sm:hidden dark:bg-gray-900">
      <Logo className="h-10 w-44 fill-black dark:fill-white" />
      <TimeDisplay className="mr-2 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300" />
    </div>
  );
}

function OuterPanel({ children }: { children: React.ReactNode }) {
  const [isOpen, setOpen] = useAtom(leftPanelOpenAtom);
  const onCollapse = () => setOpen(!isOpen);
  const location = useLocation();

  return (
    <aside
      data-test-id="left-panel"
      className={`absolute left-0 top-0 z-20 h-full w-full  bg-zinc-50 shadow-xl transition-all duration-500 sm:flex sm:w-[calc(14vw_+_16rem)] dark:bg-gray-900 dark:[color-scheme:dark] ${
        location.pathname === '/map' ? 'hidden' : ''
      } ${isOpen ? '' : '-translate-x-full'}`}
    >
      <MobileHeader />
      <section className="h-full w-full p-2 pr-0 sm:pl-1">{children}</section>
      <CollapseButton isCollapsed={!isOpen} onCollapse={onCollapse} />
    </aside>
  );
}
const SentryRoutes = Sentry.withSentryReactRouterV6Routing(Routes);
export default function LeftPanel() {
  return (
    <OuterPanel>
      <SentryRoutes>
        <Route path="/" element={<HandleLegacyRoutes />} />
        <Route
          path="/zone/:zoneId"
          element={
            <ValidZoneIdGuardWrapper>
              <ZoneDetails />
            </ValidZoneIdGuardWrapper>
          }
        />
        {/* Alternative: add /map here and have a NotFound component for anything else*/}
        <Route path="*" element={<RankingPanel />} />
      </SentryRoutes>
    </OuterPanel>
  );
}
