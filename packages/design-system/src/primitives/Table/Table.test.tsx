import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Table, type TableColumn } from './index'

interface Row {
  id: string
  name: string
  rating: number
}

const rows: Row[] = [
  { id: 'a', name: 'RedBull_Barley', rating: 1876 },
  { id: 'b', name: 'Yo', rating: 15234 },
]

const columns: [TableColumn<Row>, ...TableColumn<Row>[]] = [
  { key: 'name', header: 'Name', render: (row) => row.name },
  { key: 'rating', header: 'Rating', align: 'numeric', render: (row) => row.rating },
]

describe('Table', () => {
  it('renders a real <table> with a <caption> and one <th scope="col"> per column', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('Recent matches').tagName).toBe('CAPTION')
    const columnHeaders = screen.getAllByRole('columnheader')
    expect(columnHeaders).toHaveLength(2)
    expect(columnHeaders[0]).toHaveTextContent('Name')
    expect(columnHeaders[1]).toHaveTextContent('Rating')
  })

  it('hides the caption visually while keeping it as the region and table name', () => {
    render(
      <Table
        caption="Recent matches"
        captionHidden
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
      />,
    )
    const caption = screen.getByText('Recent matches')
    expect(caption.className).toMatch(/sr-only/)
    expect(screen.getByRole('region', { name: 'Recent matches' })).toBeInTheDocument()
  })

  it('labels the scroll region from the caption and makes it a focusable, keyboard-scrollable region', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    const region = screen.getByRole('region', { name: 'Recent matches' })
    expect(region).toHaveAttribute('tabindex', '0')
  })

  it('renders the first column as the row identity cell (<th scope="row">) and the rest as <td>', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    const rowHeaders = screen.getAllByRole('rowheader')
    expect(rowHeaders).toHaveLength(2)
    expect(rowHeaders[0]).toHaveTextContent('RedBull_Barley')
    const cells = screen.getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['1876', '15234'])
  })

  it('right-aligns a numeric column, header included, and renders its cells through type-numeric', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    const columnHeaders = screen.getAllByRole('columnheader')
    expect(columnHeaders[1].className).toMatch(/text-right/)
    const cells = screen.getAllByRole('cell')
    expect(cells[0].className).toMatch(/type-numeric/)
    expect(cells[0].className).toMatch(/text-right/)
  })

  it('does not right-align or number-format a text column', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    const rowHeaders = screen.getAllByRole('rowheader')
    expect(rowHeaders[0].className).not.toMatch(/text-right/)
    expect(rowHeaders[0].className).not.toMatch(/type-numeric/)
  })

  it('renders no row link and no hover treatment when getRowHref is absent', () => {
    render(<Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    const rowHeaders = screen.getAllByRole('rowheader')
    const tr = rowHeaders[0].closest('tr')
    expect(tr?.className).not.toMatch(/hover:bg-surface-sunken/)
  })

  it('wraps the identity cell in a real, whole-row link when getRowHref returns one, and highlights only that row', () => {
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        getRowHref={(row) => (row.id === 'a' ? `/matches/${row.id}` : undefined)}
      />,
    )
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/matches/a')
    const linkedRow = links[0].closest('tr')
    expect(linkedRow?.className).toMatch(/hover:bg-surface-sunken/)
    const rowHeaders = screen.getAllByRole('rowheader')
    const unlinkedRow = rowHeaders[1].closest('tr')
    expect(unlinkedRow?.className).not.toMatch(/hover:bg-surface-sunken/)
  })

  it('intercepts a plain left click on the row link into onNavigate', () => {
    const onNavigate = vi.fn()
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        getRowHref={(row) => `/matches/${row.id}`}
        onNavigate={onNavigate}
      />,
    )
    fireEvent.click(screen.getAllByRole('link')[0], { button: 0 })
    expect(onNavigate).toHaveBeenCalledWith('/matches/a')
  })

  it('leaves a modified click to native anchor handling', () => {
    const onNavigate = vi.fn()
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        getRowHref={(row) => `/matches/${row.id}`}
        onNavigate={onNavigate}
      />,
    )
    fireEvent.click(screen.getAllByRole('link')[0], { button: 0, metaKey: true })
    expect(onNavigate).not.toHaveBeenCalled()
  })

  it('loading: retains the caption and headers, renders the caller-supplied count of skeleton rows, no real row and no digit or dash placeholder, and announces aria-busy once on the region', () => {
    const { container } = render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        status="loading"
        skeletonRowCount={3}
      />,
    )
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    expect(screen.queryByRole('rowheader')).not.toBeInTheDocument()
    expect(screen.queryByText('1876')).not.toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText('–')).not.toBeInTheDocument()
    const skeletonRows = container.querySelectorAll('tbody tr')
    expect(skeletonRows).toHaveLength(3)
    const busyRegions = container.querySelectorAll('[aria-busy="true"]')
    expect(busyRegions).toHaveLength(1)
  })

  it('error: retains the caption and headers, and renders the caller-supplied content in one cell spanning every column', () => {
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        status="error"
        errorContent={<p>Something went wrong.</p>}
      />,
    )
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    const cell = screen.getByText('Something went wrong.').closest('td')
    expect(cell).toHaveAttribute('colspan', String(columns.length))
    expect(screen.queryByRole('rowheader')).not.toBeInTheDocument()
  })

  it('empty: retains the caption and headers, and renders the caller-supplied content in one cell spanning every column', () => {
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        status="empty"
        emptyContent={<p>No matches yet.</p>}
      />,
    )
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    const cell = screen.getByText('No matches yet.').closest('td')
    expect(cell).toHaveAttribute('colspan', String(columns.length))
  })

  it('renders no aria-busy attribute for any non-loading status', () => {
    const { container } = render(
      <Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />,
    )
    expect(container.querySelectorAll('[aria-busy]')).toHaveLength(0)
  })

  it('renders an optional footer row spanning every column', () => {
    render(
      <Table
        caption="Recent matches"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
        footer="2 matches shown"
      />,
    )
    const cell = screen.getByText('2 matches shown').closest('td')
    expect(cell).toHaveAttribute('colspan', String(columns.length))
    expect(cell?.closest('tfoot')).not.toBeNull()
  })

  it('renders no footer row when none is supplied', () => {
    const { container } = render(
      <Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />,
    )
    expect(container.querySelector('tfoot')).toBeNull()
  })

  it('dense (default) renders body cells at text-sm; prose renders them at text-md', () => {
    const { rerender } = render(
      <Table caption="Recent matches" columns={columns} rows={rows} getRowKey={(r) => r.id} />,
    )
    expect(screen.getAllByRole('rowheader')[0].className).toMatch(/text-sm/)

    rerender(
      <Table
        caption="Recent matches"
        density="prose"
        columns={columns}
        rows={rows}
        getRowKey={(r) => r.id}
      />,
    )
    expect(screen.getAllByRole('rowheader')[0].className).toMatch(/text-md/)
  })
})
