
import React, { useState, useEffect, useRef } from 'react';

import {
  Bell,
  ChevronDown,
  LogOut,
  Thermometer,
  Droplets,
  Wind,
  CheckCheck
} from 'lucide-react';

export default function Header({ page, user, onLogout }) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [readNotifications, setReadNotifications] = useState(false);

  // Refs for detecting clicks outside the dropdowns
  const notificationRef = useRef(null);
  const profileRef = useRef(null);

  // Close dropdowns when clicking anywhere outside them
  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        notificationRef.current &&
        !notificationRef.current.contains(event.target)
      ) {
        setShowNotifications(false);
      }

      if (
        profileRef.current &&
        !profileRef.current.contains(event.target)
      ) {
        setShowProfileMenu(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, []);

  const notifications = [
    {
      id: 1,
      title: 'Temperature status',
      message: 'Box temperature is within the configured range.',
      time: 'Just now',
      icon: Thermometer
    },
    {
      id: 2,
      title: 'Humidity status',
      message: 'Humidity levels are being monitored.',
      time: '2 minutes ago',
      icon: Droplets
    },
    {
      id: 3,
      title: 'Gas sensor status',
      message: 'MQ-135 sensor response is available.',
      time: '5 minutes ago',
      icon: Wind
    }
  ];

  const unreadCount = readNotifications
    ? 0
    : notifications.length;

  const userName =
    user?.name ||
    user?.email?.split('@')[0] ||
    'FreshBox User';

  const initials = userName
    .split(' ')
    .filter(Boolean)
    .map((word) => word[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  // Open notifications and close profile menu
  const handleNotificationClick = () => {
    setShowNotifications((prev) => !prev);
    setShowProfileMenu(false);
  };

  // Open profile and close notifications
  const handleProfileClick = () => {
    setShowProfileMenu((prev) => !prev);
    setShowNotifications(false);
  };

  return (
    <header className="topbar">
      <div className="crumb">
        Workspace <span>/</span> <b>{page}</b>
      </div>

      <div className="top-actions">
        <small>FreshBox workspace</small>

        {/* Notifications */}
        <div
          className="header-dropdown-wrapper"
          ref={notificationRef}
        >
          <button
            type="button"
            className={`bell ${
              showNotifications ? 'bell-active' : ''
            }`}
            aria-label="Notifications"
            aria-expanded={showNotifications}
            onClick={handleNotificationClick}
          >
            <Bell size={19} />

            {unreadCount > 0 && (
              <span className="notification-count">
                {unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="notification-dropdown">
              <div className="notification-header">
                <div>
                  <h3>Notifications</h3>

                  <p>
                    {unreadCount > 0
                      ? `${unreadCount} unread notifications`
                      : 'You are all caught up'}
                  </p>
                </div>

                <button
                  type="button"
                  className="mark-read-btn"
                  onClick={() => setReadNotifications(true)}
                  title="Mark all as read"
                >
                  <CheckCheck size={17} />
                </button>
              </div>

              <div className="notification-list">
                {notifications.map((notification) => {
                  const Icon = notification.icon;

                  return (
                    <div
                      className={`notification-item ${
                        !readNotifications ? 'unread' : ''
                      }`}
                      key={notification.id}
                    >
                      <div className="notification-icon">
                        <Icon size={18} />
                      </div>

                      <div className="notification-content">
                        <h4>{notification.title}</h4>

                        <p>{notification.message}</p>

                        <small>{notification.time}</small>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="notification-footer">
                <span>
                  FreshBox AI · Demo notifications
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Profile / Logout */}
        <div
          className="header-dropdown-wrapper"
          ref={profileRef}
        >
          <button
            type="button"
            className="profile-button"
            aria-label="Open profile menu"
            aria-expanded={showProfileMenu}
            onClick={handleProfileClick}
          >
            <div className="avatar">
              {initials}
            </div>

            <ChevronDown size={15} />
          </button>

          {showProfileMenu && (
            <div className="profile-dropdown">
              <div className="profile-info">
                <div className="avatar">
                  {initials}
                </div>

                <div>
                  <b>{userName}</b>

                  <small>
                    {user?.email || 'FreshBox account'}
                  </small>
                </div>
              </div>

              <button
                type="button"
                className="logout-dropdown-btn"
                onClick={() => {
                  setShowProfileMenu(false);
                  onLogout?.();
                }}
              >
                <LogOut size={17} />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
