// icons.jsx — line-icon set (1.6 stroke), shared via window.
// Keep visual weight consistent: 24x24 viewBox, currentColor stroke.

const Ic = ({ d, size = 18, fill = "none", stroke = 1.6, children, ...p }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill}
    stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" {...p}>
    {d ? <path d={d} /> : children}
  </svg>
);

const IconBall = (p) => (
  <Ic {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7.5l3.2 2.4-1.2 3.8h-4l-1.2-3.8z" /><path d="M12 7.5V4.5M15.2 9.9l2.8-1M14 13.7l1.7 2.5M10 13.7l-1.7 2.5M8.8 9.9l-2.8-1" /></Ic>
);
const IconClock = (p) => <Ic {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 1.8" /></Ic>;
const IconSpark = (p) => <Ic {...p} d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />;
const IconSearch = (p) => <Ic {...p}><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></Ic>;
const IconShield = (p) => <Ic {...p} d="M12 3l7 3v5.5c0 4.2-2.9 7.5-7 9-4.1-1.5-7-4.8-7-9V6z" />;
const IconShieldCheck = (p) => <Ic {...p}><path d="M12 3l7 3v5.5c0 4.2-2.9 7.5-7 9-4.1-1.5-7-4.8-7-9V6z" /><path d="M9 12l2 2 4-4.2" /></Ic>;
const IconLayers = (p) => <Ic {...p}><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></Ic>;
const IconGauge = (p) => <Ic {...p}><path d="M4 15a8 8 0 1 1 16 0" /><path d="M12 15l4-4" /><circle cx="12" cy="15" r="1.3" fill="currentColor" stroke="none" /></Ic>;
const IconArrowRight = (p) => <Ic {...p}><path d="M5 12h13" /><path d="M13 6l6 6-6 6" /></Ic>;
const IconArrowUpRight = (p) => <Ic {...p}><path d="M7 17L17 7" /><path d="M8 7h9v9" /></Ic>;
const IconCheck = (p) => <Ic {...p}><path d="M5 12.5l4.5 4.5L19 7" /></Ic>;
const IconCheckCircle = (p) => <Ic {...p}><circle cx="12" cy="12" r="9" /><path d="M8 12.2l2.6 2.6L16 9" /></Ic>;
const IconX = (p) => <Ic {...p}><path d="M6 6l12 12M18 6L6 18" /></Ic>;
const IconAlert = (p) => <Ic {...p}><path d="M12 4l9 16H3z" /><path d="M12 10v4.5M12 17.4v.1" /></Ic>;
const IconCircleDot = (p) => <Ic {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none" /></Ic>;
const IconGraph = (p) => <Ic {...p}><circle cx="6" cy="7" r="2.2" /><circle cx="18" cy="6" r="2.2" /><circle cx="16" cy="18" r="2.2" /><path d="M8 8l8-1M16.5 8l-1 8M8 8.5l7 8.5" /></Ic>;
const IconDoc = (p) => <Ic {...p}><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9.5 13h6M9.5 16h4" /></Ic>;
const IconUser = (p) => <Ic {...p}><circle cx="12" cy="8.5" r="3.5" /><path d="M5.5 19c.6-3.4 3.2-5 6.5-5s5.9 1.6 6.5 5" /></Ic>;
const IconUsers = (p) => <Ic {...p}><circle cx="9" cy="8.5" r="3" /><path d="M3.5 18.5c.5-3 2.6-4.5 5.5-4.5s5 1.5 5.5 4.5" /><path d="M16 6.2a3 3 0 0 1 0 5.6M17.5 18.5c-.2-2-1-3.3-2.3-4.1" /></Ic>;
const IconLock = (p) => <Ic {...p}><rect x="5" y="10.5" width="14" height="9.5" rx="2.4" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /><circle cx="12" cy="15" r="1.3" fill="currentColor" stroke="none" /></Ic>;
const IconKey = (p) => <Ic {...p}><circle cx="8" cy="8" r="4" /><path d="M11 11l8 8M16 16l2-2M18.5 18.5l1.5-1.5" /></Ic>;
const IconCrown = (p) => <Ic {...p}><path d="M4 8l3.5 3L12 5l4.5 6L20 8l-1.5 10h-13z" /></Ic>;
const IconBolt = (p) => <Ic {...p} d="M13 3L5 13h6l-1 8 8-10h-6z" />;
const IconLink = (p) => <Ic {...p}><path d="M9.5 14.5l5-5" /><path d="M8 12l-1.5 1.5a3.5 3.5 0 0 0 5 5L13 17" /><path d="M16 12l1.5-1.5a3.5 3.5 0 0 0-5-5L11 7" /></Ic>;
const IconMenu = (p) => <Ic {...p}><path d="M4 7h16M4 12h16M4 17h16" /></Ic>;
const IconLogout = (p) => <Ic {...p}><path d="M14 4H6v16h8" /><path d="M10 12h10M17 8l4 4-4 4" /></Ic>;
const IconRefresh = (p) => <Ic {...p}><path d="M4 12a8 8 0 0 1 13.7-5.6L20 8" /><path d="M20 4v4h-4" /><path d="M20 12a8 8 0 0 1-13.7 5.6L4 16" /><path d="M4 20v-4h4" /></Ic>;
const IconEye = (p) => <Ic {...p}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.6" /></Ic>;
const IconFlag = (p) => <Ic {...p}><path d="M6 21V4M6 5h11l-2 3 2 3H6" /></Ic>;
const IconScale = (p) => <Ic {...p}><path d="M12 4v16M7 20h10M5 8h14M5 8l-2.5 5h5zM19 8l-2.5 5h5z" /></Ic>;

Object.assign(window, {
  IconBall, IconClock, IconSpark, IconSearch, IconShield, IconShieldCheck, IconLayers,
  IconGauge, IconArrowRight, IconArrowUpRight, IconCheck, IconCheckCircle, IconX, IconAlert,
  IconCircleDot, IconGraph, IconDoc, IconUser, IconUsers, IconLock, IconKey, IconCrown,
  IconBolt, IconLink, IconMenu, IconLogout, IconRefresh, IconEye, IconFlag, IconScale,
});
