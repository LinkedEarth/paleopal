import React from 'react';
import ICONS from '../styles/iconTheme';

const Icon = ({ name, className = '' }) => {
  const icon = ICONS[name];
  if (!icon) return null;
  return React.cloneElement(icon, { className: `${icon.props.className || ''} ${className}`.trim() });
};

export default Icon; 