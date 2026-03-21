import * as React from "react";

const BaseIcon = ({
  children,
  ...props
}: React.SVGProps<SVGSVGElement> & { children: React.ReactNode }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    {children}
  </svg>
);

export const IconUsers = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M15 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="8" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </BaseIcon>
);

export const IconHome = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M3 10l9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V10z" />
    <path d="M9 22V12h6v10" />
  </BaseIcon>
);

export const IconBed = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M4 5v14" />
    <path d="M4 15h16v-5a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v5" />
    <path d="M20 15v4" />
    <path d="M4 11h16" />
  </BaseIcon>
);

export const IconCutlery = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
    <path d="M7 2v20" />
    <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3zm0 0v7" />
  </BaseIcon>
);

export const IconBathtub = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M4 11h16v4a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-4z" />
    <path d="M6 19v2" />
    <path d="M18 19v2" />
    <path d="M2 11h20" />
    <path d="M18 11V5a2 2 0 0 0-2-2h-3" />
    <path d="M13 2h2" />
    <path d="M13 5h2" />
  </BaseIcon>
);

export const IconDrops = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M7 16.3c-1.5 0-2.5-1.2-2.5-2.7 0-2 2.5-5.3 2.5-5.3s2.5 3.3 2.5 5.3c0 1.5-1.1 2.7-2.5 2.7z" />
    <path d="M15 21c-2 0-3.5-1.5-3.5-3.5 0-2.5 3.5-7 3.5-7s3.5 4.5 3.5 7c0 2-1.5 3.5-3.5 3.5z" />
    <path d="M19 12.5c-1 0-1.5-.5-1.5-1.5 0-1.5 1.5-3.5 1.5-3.5s1.5 2 1.5 3.5c0 1-.5 1.5-1.5 1.5z" />
  </BaseIcon>
);

export const IconFlame = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
  </BaseIcon>
);

export const IconTent = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M12 4L3 20h18z" />
    <path d="M12 4v16" />
    <path d="M8 20l4-5" />
    <path d="M16 20l-4-5" />
  </BaseIcon>
);

export const IconWifi = (props: React.SVGProps<SVGSVGElement>) => (
  <BaseIcon {...props}>
    <path d="M5 13a10 10 0 0 1 14 0" />
    <path d="M8.5 16.5a5 5 0 0 1 7 0" />
    <path d="M2 9.5a15 15 0 0 1 20 0" />
    <circle cx="12" cy="20" r="1.5" fill="currentColor" stroke="none" />
  </BaseIcon>
);

export const facilityIcons = {
  users: IconUsers,
  home: IconHome,
  bed: IconBed,
  cutlery: IconCutlery,
  bathtub: IconBathtub,
  drops: IconDrops,
  flame: IconFlame,
  tent: IconTent,
  wifi: IconWifi,
} as const;

export type FacilityIconName = keyof typeof facilityIcons;

export function FacilityIcon({
  name,
  ...props
}: React.SVGProps<SVGSVGElement> & { name: FacilityIconName }) {
  const IconComponent = facilityIcons[name];
  return <IconComponent {...props} />;
}
