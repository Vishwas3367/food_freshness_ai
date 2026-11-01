
import React from 'react';

import {
  Search,
  CalendarDays,
  Clock,
  Scale
} from 'lucide-react';

import FoodCard from '../components/FoodCard.jsx';

export default function Inventory({
  items = [],
  category,
  setCategory,
  search,
  setSearch,
  onSelect
}) {
  const categories = [
    'All items',
    'Fruit',
    'Vegetable',
    'Fresh',
    'Use soon',
    'Critical'
  ];

  const formatDate = (value) => {
    if (!value) return 'Not recorded';

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return 'Not recorded';
    }

    return date.toLocaleDateString(undefined, {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  };

  const formatTime = (value) => {
    if (!value) return 'Not recorded';

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return 'Not recorded';
    }

    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <>
      {/* Page Heading */}
      <div className="welcome">
        <div>
          <small className="eyebrow">
            YOUR FOOD, ORGANIZED
          </small>

          <h1>Food Inventory</h1>

          <p>
            Browse every fruit and vegetable currently stored
            in your FreshBox.
          </p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="toolbar">
        <div className="tabs">
          {categories.map((itemCategory) => (
            <button
              key={itemCategory}
              className={
                category === itemCategory ? 'chosen' : ''
              }
              onClick={() => setCategory(itemCategory)}
            >
              {itemCategory === 'Fruit'
                ? 'Fruits'
                : itemCategory === 'Vegetable'
                ? 'Vegetables'
                : itemCategory}
            </button>
          ))}
        </div>

        <div className="search">
          <Search size={16} />

          <input
            type="text"
            placeholder="Search food..."
            value={search}
            onChange={(event) =>
              setSearch(event.target.value)
            }
          />
        </div>
      </div>

      {/* Result Count */}
      <p className="result-count">
        Showing {items.length} food item(s)
      </p>

      {/* Inventory Items */}
      {items.length === 0 ? (
        <div className="empty-inventory">
          <div className="empty-icon">🥬</div>

          <h2>No food items found</h2>

          <p>
            Add fruits or vegetables from your Dashboard,
            or change your search or category filter.
          </p>
        </div>
      ) : (
        <div className="food-grid">
          {items.map((item) => (
            <div
              className="inventory-item"
              key={item.id}
            >
              <FoodCard
                item={item}
                onClick={onSelect}
              />

              {(item.quantityKg !== undefined ||
                item.addedAt) && (
                <div className="inventory-meta">
                  {item.quantityKg !== undefined && (
                    <span>
                      <Scale size={14} />

                      {Number(item.quantityKg).toFixed(2)} kg
                    </span>
                  )}

                  {item.addedAt && (
                    <>
                      <span>
                        <CalendarDays size={14} />

                        {formatDate(item.addedAt)}
                      </span>

                      <span>
                        <Clock size={14} />

                        {formatTime(item.addedAt)}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
